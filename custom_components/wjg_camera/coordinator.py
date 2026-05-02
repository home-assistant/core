"""
WJG Camera Coordinator
======================
Verwaltet Verbindung, State und Datenabruf zur Kamera.
Unterstützt: RTSP, HTTP Snapshot, XM SDK (Port 34567), ONVIF.
"""
# pylint: disable=broad-exception-caught

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import socket
import struct
import time
from datetime import timedelta
from typing import Any

import aiohttp
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


# Konstanten lokal definieren, um zirkulären Import zu vermeiden
CONF_PROTOCOL = "protocol"
CONF_HTTP_RETRIES = "http_retries"
CONF_RTSP_PATH = "rtsp_path"
CONF_RTSP_PORT = "rtsp_port"
CONF_SNAPSHOT_PATH = "snapshot_path"
DEFAULT_HTTP_PORT = 80
DEFAULT_HTTP_RETRIES = 1
DEFAULT_RTSP_PATH = "/user=admin&password=&channel=1&stream=0.sdp?real_stream"
DEFAULT_SNAPSHOT_PATH = "/webcapture.jpg?command=snap&channel=1"
DEFAULT_XM_PORT = 34567
DOMAIN = "wjg_camera"
PROTOCOL_HTTP = "http_only"
PROTOCOL_RTSP = "rtsp"
PROTOCOL_XM = "xm_sdk"

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=10)

# XM SDK Message IDs
XM_LOGIN_REQ       = 0x03E8  # 1000
XM_LOGIN_RSP       = 0x03E9
XM_KEEPALIVE_REQ   = 0x03EE  # 1006
XM_RECORD_START    = 0x041A
XM_RECORD_STOP     = 0x041B
XM_FILELIST_REQ    = 0x0592
XM_MOTION_REQ      = 0x0144


async def _await_if_needed(value: Any) -> Any:
    """Async und sync Rueckgaben einheitlich behandeln."""
    if inspect.isawaitable(value):
        return await value
    return value

def xm_packet(session_id: int, seq: int, msg_id: int, data: dict) -> bytes:
    """Erstellt ein XM SDK Binärpaket."""
    payload = json.dumps(data, separators=(",", ":")).encode()
    # FF 01 00 00 | SessionID(4) | Sequence(4) | 00 00 | MsgID(2) | DataLen(4)
    header = struct.pack(
        "<BBHIIBBHI",
        0xFF, 0x01, 0x0000,
        session_id, seq,
        0x00, 0x00,
        msg_id, len(payload)
    )
    return header + payload

def xm_parse(data: bytes) -> tuple[int, dict]:
    """Parst ein XM SDK Antwortpaket. Gibt (msg_id, body_dict) zurück."""
    if len(data) < 20:
        return 0, {}
    _, _, _, _, _, _, _, msg_id, data_len = struct.unpack("<BBHIIBBHI", data[:20])
    body_bytes = data[20: 20 + data_len]
    try:
        body = json.loads(body_bytes.decode("utf-8").strip("\x00"))
    except Exception:
        body = {}
    return msg_id, body


class XMClient:
    """Synchroner XM SDK TCP-Client (läuft in executor)."""

    def __init__(self, host: str, port: int, username: str, password: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self._sock: socket.socket | None = None
        self._session_id = 0
        self._seq = 0

    def connect(self, timeout: float = 5.0) -> bool:
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(timeout)
            self._sock.connect((self.host, self.port))
            return self._login()
        except Exception as e:
            _LOGGER.debug("XM connect fehlgeschlagen: %s", e)
            return False

    def _send_recv(self, msg_id: int, data: dict, recv_size: int = 2048) -> dict:
        if not self._sock:
            return {}
        pkt = xm_packet(self._session_id, self._seq, msg_id, data)
        self._seq += 1
        self._sock.sendall(pkt)
        resp = self._sock.recv(recv_size)
        _, body = xm_parse(resp)
        return body

    def _login(self) -> bool:
        # Passwort-Hash nach XM-Methode (MD5 mit Padding)
        import hashlib
        raw = hashlib.md5(self.password.encode()).hexdigest().upper()
        pwd_hash = ""
        for i in range(0, 32, 2):
            c = (ord(raw[i]) + ord(raw[i+1])) % 0x62
            pwd_hash += chr(c + (0x41 if c < 0xA else 0x30 + 0x39 - 9))
        pwd_hash = pwd_hash[:8] if self.password else ""

        resp = self._send_recv(XM_LOGIN_REQ, {
            "EncryptType": "MD5",
            "LoginType": "DVRIP-Web",
            "PassWord": pwd_hash,
            "UserName": self.username,
        })
        ret = resp.get("Ret", -1)
        if ret in (100, 101):
            self._session_id = int(resp.get("SessionID", "0x0"), 16)
            return True
        _LOGGER.warning("XM Login fehlgeschlagen, Ret=%s", ret)
        return False

    def keepalive(self) -> bool:
        resp = self._send_recv(XM_KEEPALIVE_REQ, {"Type": "KeepAlive"})
        return resp.get("Ret", 0) == 100

    def start_recording(self, channel: int = 0) -> bool:
        resp = self._send_recv(XM_RECORD_START, {
            "Action": "StartRecord", "Parameter": {"Channel": channel}
        })
        return resp.get("Ret", 0) == 100

    def stop_recording(self, channel: int = 0) -> bool:
        resp = self._send_recv(XM_RECORD_STOP, {
            "Action": "StopRecord", "Parameter": {"Channel": channel}
        })
        return resp.get("Ret", 0) == 100

    def get_file_list(self, channel: int = 0, max_files: int = 50) -> list[dict]:
        resp = self._send_recv(XM_FILELIST_REQ, {
            "Action": "FindNextFile", "FileType": "h264",
            "StartTime": "2000-01-01 00:00:00",
            "EndTime": "2099-12-31 23:59:59",
            "Channel": channel, "Count": max_files
        }, recv_size=16384)
        return resp.get("Found", [])

    def get_motion_state(self) -> bool:
        resp = self._send_recv(XM_MOTION_REQ, {
            "Name": "MotionDetect", "SessionID": hex(self._session_id)
        })
        return resp.get("Ret", 0) == 100

    def ptz_command(self, code: int, speed: int = 5, channel: int = 0) -> bool:
        resp = self._send_recv(
            0x0601,
            {
                "Parameter": {
                    "Channel": channel,
                    "CommandValue": code,
                    "Speed": speed,
                }
            },
        )
        return resp.get("Ret", 0) == 100

    def disconnect(self) -> None:
        """Offene Socket-Verbindung schliessen."""
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None


class WJGCameraCoordinator(DataUpdateCoordinator):
    """Haupt-Koordinator für die WJG Kamera."""

    @staticmethod
    def _normalize_http_retries(value: Any) -> int:
        """Retry-Wert robust auf den erlaubten Bereich 0..5 bringen."""
        try:
            retries = int(value)
        except (TypeError, ValueError):
            return DEFAULT_HTTP_RETRIES
        return max(0, min(5, retries))

    def is_adb_proxy(self) -> bool:
        """Erkennt, ob ADB-Proxy-Modus aktiv ist (localhost mit Port 8080/8081)."""
        return (
            self.host in ("127.0.0.1", "localhost")
            and self.rtsp_port == 8080
            and self.http_port == 8081
        )

    async def async_adb_proxy_check(self) -> bool:
        """Prüft, ob ADB-Proxy-Port erreichbar ist."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://127.0.0.1:8081/") as resp:
                    return resp.status == 200
        except Exception:
            return False

    # Beispiel für automatisches Umschalten auf ADB-Proxy, falls Ports erkannt werden
    async def async_prepare_connection(self) -> None:
        """ADB-Proxy-Erreichbarkeit bei lokalem Tunnel pruefen."""
        if self.is_adb_proxy():
            ok = await self.async_adb_proxy_check()
            if not ok:
                _LOGGER.warning(
                    "ADB-Proxy-Port 8081 nicht erreichbar. Bitte ADB-Tunnel pruefen!"
                )

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.entry = entry
        self.host: str = entry.data[CONF_HOST]
        self.username: str = entry.data.get(CONF_USERNAME, "admin")
        self.password: str = entry.data.get(CONF_PASSWORD, "")
        self.protocol: str = entry.data.get(CONF_PROTOCOL, PROTOCOL_RTSP)
        self.rtsp_port: int = entry.data.get(CONF_RTSP_PORT, 554)
        self.http_port: int = entry.data.get(CONF_PORT, DEFAULT_HTTP_PORT)
        self.xm_port: int = DEFAULT_XM_PORT
        self.rtsp_path: str = entry.data.get(CONF_RTSP_PATH, DEFAULT_RTSP_PATH)
        self.snapshot_path: str = entry.data.get(
            CONF_SNAPSHOT_PATH, DEFAULT_SNAPSHOT_PATH
        )
        options = getattr(entry, "options", {}) or {}
        self.http_retries: int = self._normalize_http_retries(
            options.get(
                CONF_HTTP_RETRIES,
                entry.data.get(CONF_HTTP_RETRIES, DEFAULT_HTTP_RETRIES),
            )
        )
        self._session: aiohttp.ClientSession | None = None
        self._xm: XMClient | None = None
        self._recording: bool = False
        self._motion: bool = False
        self._last_motion_time: float = 0
        self._onvif = None
        if self.protocol == "onvif":
            try:
                from onvif import ONVIFCamera

                self._onvif = ONVIFCamera(
                    self.host,
                    entry.data.get("onvif_port", 8899),
                    self.username,
                    self.password
                )
            except Exception as e:
                _LOGGER.error("ONVIF-Initialisierung fehlgeschlagen: %s", e)

    async def async_onvif_ptz(self, cmd: str, speed: float = 0.5) -> bool:
        """ONVIF PTZ-Befehl senden (up/down/left/right/zoom_in/zoom_out/stop)."""
        if not self._onvif:
            return False
        try:
            media_service = self._onvif.create_media_service()
            ptz_service = self._onvif.create_ptz_service()
            profiles = await _await_if_needed(media_service.GetProfiles())
            profile = profiles[0]
            req = ptz_service.create_type('ContinuousMove')
            req.ProfileToken = profile.token
            req.Velocity = {}
            if cmd == "up":
                req.Velocity = {"PanTilt": {"x": 0, "y": speed}}
            elif cmd == "down":
                req.Velocity = {"PanTilt": {"x": 0, "y": -speed}}
            elif cmd == "left":
                req.Velocity = {"PanTilt": {"x": -speed, "y": 0}}
            elif cmd == "right":
                req.Velocity = {"PanTilt": {"x": speed, "y": 0}}
            elif cmd == "zoom_in":
                req.Velocity = {"Zoom": {"x": speed}}
            elif cmd == "zoom_out":
                req.Velocity = {"Zoom": {"x": -speed}}
            elif cmd == "stop":
                await _await_if_needed(ptz_service.Stop({'ProfileToken': profile.token}))
                return True
            else:
                return False
            await _await_if_needed(ptz_service.ContinuousMove(req))
            return True
        except Exception as e:
            _LOGGER.error("ONVIF PTZ-Befehl fehlgeschlagen: %s", e)
            return False

    async def async_onvif_stream_url(self) -> str | None:
        """ONVIF Stream-URL abrufen."""
        if not self._onvif:
            return None
        try:
            media_service = self._onvif.create_media_service()
            profiles = await _await_if_needed(media_service.GetProfiles())
            profile = profiles[0]
            req = media_service.create_type('GetStreamUri')
            req.ProfileToken = profile.token
            req.StreamSetup = {"Stream": "RTP-Unicast", "Transport": {"Protocol": "RTSP"}}
            uri = await _await_if_needed(media_service.GetStreamUri(req))
            return uri.Uri
        except Exception as e:
            _LOGGER.error("ONVIF Stream-URL konnte nicht abgerufen werden: %s", e)
            return None

    @property
    def rtsp_url(self) -> str:
        u = f"admin:{self.password}@" if self.password else f"{self.username}:@"
        return f"rtsp://{u}{self.host}:{self.rtsp_port}{self.rtsp_path}"

    @property
    def snapshot_url(self) -> str:
        return f"http://{self.host}:{self.http_port}{self.snapshot_path}"

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def motion_detected(self) -> bool:
        """True zurueckgeben, solange die letzte Bewegung frisch genug ist."""
        return time.time() - self._last_motion_time < 30

    @property
    def last_motion_time(self) -> float:
        return self._last_motion_time

    async def async_setup(self) -> None:
        """Verbindung herstellen und testen."""
        self._session = aiohttp.ClientSession()
        session = self._session
        assert session is not None

        # HTTP-Erreichbarkeit prüfen
        try:
            async with async_timeout.timeout(5):
                async with session.get(
                    f"http://{self.host}:{self.http_port}/",
                    allow_redirects=True
                ) as resp:
                    _LOGGER.debug(
                        "Kamera HTTP erreichbar, Status: %s", resp.status
                    )
        except Exception as e:
            _LOGGER.warning("HTTP nicht erreichbar: %s — versuche RTSP-only", e)

        # XM SDK verbinden (in executor, da synchron)
        if self.protocol == PROTOCOL_XM:
            await self.hass.async_add_executor_job(self._setup_xm)

        await self.async_refresh()

    def _setup_xm(self) -> None:
        """XM SDK Client initialisieren (blockierend, im executor)."""
        client = XMClient(self.host, self.xm_port, self.username, self.password)
        if client.connect():
            self._xm = client
            _LOGGER.info(
                "XM SDK Verbindung erfolgreich zu %s:%s",
                self.host,
                self.xm_port,
            )
        else:
            _LOGGER.warning("XM SDK nicht verfügbar — Fallback auf HTTP")

    async def _async_update_data(self) -> dict[str, Any]:
        """Kamera-Status aktualisieren."""
        data: dict[str, Any] = {
            "available": False,
            "recording": self._recording,
            "motion": self.motion_detected,
            "files": [],
        }

        # Snapshot abrufen um Erreichbarkeit zu prüfen
        session = self._session
        if session is not None:
            try:
                async with async_timeout.timeout(5):
                    async with session.get(
                        self.snapshot_url, allow_redirects=True
                    ) as resp:
                        if resp.status == 200:
                            data["available"] = True
                            ct = resp.headers.get("Content-Type", "")
                            if "image" in ct:
                                data["snapshot_bytes"] = await resp.read()
            except Exception as e:
                _LOGGER.debug("Snapshot fehlgeschlagen: %s", e)

        # XM Keepalive + Status
        if self._xm:
            try:
                ok = await self.hass.async_add_executor_job(self._xm.keepalive)
                if ok:
                    data["available"] = True
            except Exception as e:
                _LOGGER.debug("XM Keepalive fehlgeschlagen: %s — reconnect", e)
                await self.hass.async_add_executor_job(self._setup_xm)

        return data

    async def _async_http_get_data(
        self,
        url: str,
        timeout_seconds: int,
        retries: int | None = None,
        as_json: bool = False,
    ) -> bytes | dict[str, Any] | None:
        """HTTP GET mit kleinem Retry für transiente Fehler.

        Gibt bei Erfolg gelesene Daten (bytes oder dict) zurück, sonst None.
        """
        if not self._session:
            return None

        effective_retries = self.http_retries if retries is None else retries
        attempts = max(1, effective_retries + 1)
        for attempt in range(attempts):
            try:
                async with async_timeout.timeout(timeout_seconds):
                    async with self._session.get(url) as resp:
                        if resp.status == 200:
                            if as_json:
                                return await resp.json()
                            return await resp.read()
            except Exception as e:
                _LOGGER.debug("HTTP GET fehlgeschlagen (%s): %s", url, e)

            if attempt < attempts - 1:
                await asyncio.sleep(0)

        return None

    async def async_set_recording(self, enabled: bool) -> bool:
        """Aufnahme starten oder stoppen."""
        xm_client = self._xm
        if xm_client is not None:
            if enabled:
                ok = await self.hass.async_add_executor_job(
                    xm_client.start_recording,
                    0,
                )
            else:
                ok = await self.hass.async_add_executor_job(
                    xm_client.stop_recording,
                    0,
                )
            if ok:
                self._recording = enabled
                return True

        # HTTP-Fallback (manche Kameras)
        if self._session:
            cmd = "start" if enabled else "stop"
            url = f"http://{self.host}:{self.http_port}/cgi-bin/record?cmd={cmd}&channel=1"
            data = await self._async_http_get_data(url, timeout_seconds=5)
            if isinstance(data, (bytes, bytearray)):
                self._recording = enabled
                return True
        return False

    async def async_get_file_list(self) -> list[dict]:
        """Dateiliste von der Kamera abrufen."""
        xm_client = self._xm
        if xm_client is not None:
            files = await self.hass.async_add_executor_job(
                xm_client.get_file_list,
                0,
                50,
            )
            return files

        # HTTP-Fallback
        if self._session:
            url = f"http://{self.host}:{self.http_port}/cgi-bin/fileman"
            data = await self._async_http_get_data(
                url,
                timeout_seconds=10,
                as_json=True,
            )
            if isinstance(data, dict):
                return data.get("files", [])
        return []

    async def async_snapshot(self) -> bytes | None:
        """Aktuelles Bild von der Kamera laden."""
        if not self._session:
            return None
        data = await self._async_http_get_data(
            self.snapshot_url,
            timeout_seconds=5,
        )
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
        return None

    async def async_ptz_command(self, cmd: str, speed: int = 5) -> bool:
        """PTZ-Steuerbefehl senden (Start/Stop Up/Down/Left/Right/Zoom)."""
        ptz_map = {
            "up": 0x10, "down": 0x11, "left": 0x12, "right": 0x13,
            "zoom_in": 0x01, "zoom_out": 0x02, "focus_in": 0x03,
            "focus_out": 0x04, "stop": 0xFF
        }
        if cmd not in ptz_map:
            _LOGGER.warning("Unbekannter PTZ-Befehl: %s", cmd)
            return False

        if self._xm:
            code = ptz_map[cmd]
            try:
                return await self.hass.async_add_executor_job(
                    self._xm.ptz_command, code, speed, 0
                )
            except Exception as e:
                _LOGGER.error("PTZ-Befehl fehlgeschlagen: %s", e)

        # HTTP-Fallback
        if self._session:
            url = (f"http://{self.host}:{self.http_port}/cgi-bin/ptz"
                   f"?channel=1&cmd={cmd}&speed={speed}")
            data = await self._async_http_get_data(url, timeout_seconds=3)
            return isinstance(data, (bytes, bytearray))
        return False

    async def async_shutdown(self) -> None:
        """Verbindungen schließen."""
        if self._session:
            await self._session.close()
            self._session = None
        if self._xm:
            await self.hass.async_add_executor_job(self._xm.disconnect)
            self._xm = None
