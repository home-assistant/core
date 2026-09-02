"""Asynchronous client for Netis routers (ubus over HTTP).

The router exposes a single JSON-RPC 2.0 endpoint ``POST /ubus`` backed by an
OpenWrt ubus daemon. Authentication is done with an AES-128-CBC encrypted
password using a server provided random key.

See ROUTER_API_REFERENCE.md for the full protocol description (all endpoints
were verified against a real MW5630 unit running firmware 4.0.260701.100631).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

import aiohttp
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .const import (
    AES_IV,
    ANONYMOUS_TOKEN,
    DEFAULT_USERNAME,
    ERR_OK,
    ERR_PERMISSION_DENIED,
    LOGIN_TIMEOUT,
    UBUS_CUSTOMER,
    UBUS_HOSTS,
    UBUS_LTE_INFO,
    UBUS_MWAN3,
    UBUS_REBOOT,
    UBUS_SYSTEM_INFO,
    UBUS_WIFI_CFG,
    WIFI_APPLY_TIMEOUT,
    WRITE_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class NetisError(Exception):
    """Base error for the Netis client."""


class NetisAuthError(NetisError):
    """Raised when login fails (wrong credentials / locked out)."""


class NetisConnectionError(NetisError):
    """Raised when the router cannot be reached."""


@dataclass
class NetisDevice:
    """A single connected client reported by the router."""

    mac: str
    name: str | None
    ip: str | None
    online: bool
    wired: bool
    wifi_24g: bool
    wifi_5g: bool
    guest: bool
    up_speed: int
    down_speed: int
    up_bytes: int
    down_bytes: int
    connected_seconds: int


@dataclass
class NetisData:
    """Aggregated snapshot of everything polled from the router."""

    # system / traffic
    model: str | None = None
    firmware: str | None = None
    hardware_version: str | None = None
    uptime: int | None = None
    wan_in_speed: int | None = None
    wan_out_speed: int | None = None
    wan_in_bytes: int | None = None
    wan_out_bytes: int | None = None
    # WAN connectivity
    wan_online: bool | None = None
    wan_interfaces: dict[str, str] = field(default_factory=dict)
    # LAN ports
    ports: list[dict[str, Any]] = field(default_factory=list)
    # LTE / 4G
    lte_connected: bool | None = None
    lte_rsrp: float | None = None
    lte_rsrq: float | None = None
    lte_rssi: float | None = None
    lte_mode: str | None = None
    lte_isp: str | None = None
    lte_ip: str | None = None
    lte_imei: str | None = None
    # WiFi (per band: 2G / 5G)
    wifi_enabled: dict[str, bool | None] = field(default_factory=dict)
    wifi_txpower: dict[str, str | None] = field(default_factory=dict)
    # LED indicator (front-panel lights)
    led_on: bool | None = None
    # devices
    devices: list[NetisDevice] = field(default_factory=list)


def _encrypt_password(password: str, rand_key: str) -> str:
    """Encrypt ``password`` exactly as the router firmware expects.

    ``rand_key`` is a 64 hex char string returned by ``rkey.get_rand_key``:
      * first 32 hex chars -> key_index (sent back prefixed to the ciphertext)
      * last 32 hex chars   -> the 16 byte AES key
    """
    key_index = rand_key[:32]
    aes_key = bytes.fromhex(rand_key[32:64])
    padder = padding.PKCS7(128).padder()
    padded = padder.update(password.encode("utf-8")) + padder.finalize()
    encryptor = Cipher(algorithms.AES(aes_key), modes.CBC(AES_IV)).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return key_index + ciphertext.hex()


class NetisClient:
    """Thin async wrapper around the ubus JSON-RPC API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str = DEFAULT_USERNAME,
        password: str = "",
    ) -> None:
        self._session = session
        self._host = host.rstrip("/")
        self._base = f"http://{self._host}"
        self._username = username
        self._password = password
        self._token: str | None = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Low level transport
    # ------------------------------------------------------------------
    async def _post(
        self, payload: dict[str, Any], total_timeout: float = LOGIN_TIMEOUT
    ) -> dict[str, Any]:
        """POST a single JSON-RPC payload and return the parsed result."""
        try:
            async with self._session.post(
                f"{self._base}/ubus",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=total_timeout),
            ) as resp:
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise NetisConnectionError(
                f"Cannot reach router at {self._base}: {err}"
            ) from err
        except asyncio.TimeoutError as err:
            raise NetisConnectionError(
                f"Timeout reaching router at {self._base}"
            ) from err

    async def _rpc(
        self,
        token: str,
        obj: str,
        method: str,
        args: dict[str, Any] | None = None,
        total_timeout: float = LOGIN_TIMEOUT,
    ) -> list:
        """Call ``obj.method`` and return the ubus ``result`` array.

        The firmware has two distinct error signalling layers:
          * JSON-RPC level: ``{"error": {"code": -32002}}`` for session/access
            denial (invalid or expired token) — no ``result`` key at all.
          * ubus level: ``[6]`` (ERR_PERMISSION_DENIED) inside the result array.
        Both must map to a permission-denied result so that ``call()`` can
        trigger re-login. We normalise the JSON-RPC-level error to ``[6]``.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call",
            "params": [token, obj, method, args or {}],
        }
        data = await self._post(payload, total_timeout=total_timeout)
        if "result" in data:
            return data["result"]
        # JSON-RPC-level error (no "result" key). Map access-denied codes
        # (-32002 etc.) to ubus code 6 so call() can re-login automatically.
        if "error" in data:
            code = data["error"].get("code", 0)
            if code < -32000:  # JSON-RPC access-denied family
                return [ERR_PERMISSION_DENIED]
            raise NetisError(f"Router JSON-RPC error {code}: {data['error'].get('message', '')}")
        raise NetisError(f"Unexpected router response: {data}")

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    async def login(self) -> str:
        """Authenticate against the router and store the session token."""
        try:
            result = await self._rpc(ANONYMOUS_TOKEN, "rkey", "get_rand_key")
        except NetisError as err:
            raise NetisConnectionError(f"get_rand_key failed: {err}") from err

        if not result or result[0] != ERR_OK:
            raise NetisAuthError(f"Failed to obtain login key: {result}")

        rand_key = result[1]["rand_key"]
        encrypted = _encrypt_password(self._password, rand_key)

        result = await self._rpc(
            ANONYMOUS_TOKEN,
            "rkey.session",
            "login",
            {"username": self._username, "password": encrypted},
        )
        if not result or result[0] != ERR_OK or len(result) < 2:
            raise NetisAuthError(f"Login rejected by router: {result}")
        session = result[1]
        if "ubus_rpc_session" not in session:
            err_code = session.get("ErrCode")
            raise NetisAuthError(
                f"Login failed (ErrCode={err_code}); check credentials"
            )
        self._token = session["ubus_rpc_session"]
        _LOGGER.debug("Logged into %s, token acquired", self._host)
        return self._token

    async def _ensure_token(self) -> str:
        if self._token is None:
            await self.login()
        assert self._token is not None
        return self._token

    async def call(
        self,
        obj: str,
        method: str,
        args: dict[str, Any] | None = None,
        retry: bool = True,
        total_timeout: float = LOGIN_TIMEOUT,
    ) -> Any:
        """Call ``obj.method`` once and re-login on permission errors."""
        async with self._lock:
            token = await self._ensure_token()
            result = await self._rpc(token, obj, method, args, total_timeout)
            if result and result[0] == ERR_PERMISSION_DENIED and retry:
                _LOGGER.debug(
                    "Token expired on %s.%s, re-logging in", obj, method
                )
                self._token = None
                await self.login()
                result = await self._rpc(self._token, obj, method, args, total_timeout)
            if not result or result[0] != ERR_OK:
                raise NetisError(
                    f"{obj}.{method} failed with ubus code {result[0] if result else 'empty'}"
                )
            return result[1] if len(result) > 1 else None

    # ------------------------------------------------------------------
    # High level endpoints (all verified against real hardware)
    # ------------------------------------------------------------------
    async def get_system_info(self) -> dict[str, Any]:
        """routerd.info - model/firmware/uptime/traffic/LAN ports."""
        return await self.call(*UBUS_SYSTEM_INFO)

    async def get_hosts(self) -> dict[str, Any]:
        """devices_app.get_host_info - connected + offline clients."""
        return await self.call(*UBUS_HOSTS)

    async def get_wan_status(self) -> dict[str, Any]:
        """mwan3.status - per-WAN-interface connectivity."""
        return await self.call(*UBUS_MWAN3)

    async def get_lte_info(self) -> dict[str, Any]:
        """lte_ubus.LteInfo - 4G signal / connection details."""
        return await self.call(*UBUS_LTE_INFO)

    async def get_customer_info(self) -> dict[str, Any]:
        """uci.get customer info - brand / model / hostname."""
        return await self.call(
            *UBUS_CUSTOMER, {"config": "customer", "section": "info"}
        )

    async def get_wifi_config(self) -> dict[str, Any]:
        """uci.get wificfg - per-band enable / TxPower / SSID."""
        return await self.call(*UBUS_WIFI_CFG, {"config": "wificfg"})

    async def _set_and_apply(
        self, config: str, section: str, values: dict[str, str], what: str
    ) -> None:
        """uci.set + uci.apply, capped end-to-end so HA never hangs.

        On this firmware the uci write/apply path occasionally blocks for
        10+ seconds (rpcd serialises config writes and can throttle rapid
        successive calls). Since ``uci.set`` commits to the running config
        immediately and the value persists even when ``uci.apply`` is a
        no-op (returns ubus code 5) or its reply is lost, we cap the whole
        operation at ``WRITE_TIMEOUT`` and confirm the resulting state on
        the next coordinator poll.
        """
        try:
            await asyncio.wait_for(
                self._set_and_apply_inner(config, section, values, what),
                timeout=WRITE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "%s write to %s on %s did not complete within %ss; the change "
                "may still apply in the background - will confirm on next poll",
                what,
                config,
                self._host,
                WRITE_TIMEOUT,
            )

    async def _set_and_apply_inner(
        self, config: str, section: str, values: dict[str, str], what: str
    ) -> None:
        """Inner helper performing the set + apply, holding the lock."""
        async with self._lock:
            await self.call(
                "uci",
                "set",
                {"config": config, "section": section, "values": values},
                total_timeout=WRITE_TIMEOUT,
            )
            try:
                await self.call(
                    "uci",
                    "apply",
                    {"timeout": "60"},
                    total_timeout=WIFI_APPLY_TIMEOUT,
                )
            except NetisConnectionError as err:
                _LOGGER.info(
                    "%s apply reply not received within %ss on %s "
                    "(change is committed); will confirm on next poll: %s",
                    what,
                    WIFI_APPLY_TIMEOUT,
                    self._host,
                    err,
                )
            except NetisError as err:
                # apply returns ubus code 5 on some firmwares when the session
                # lacks the apply ACL - the uci.set above is still committed,
                # so this is non-fatal.
                _LOGGER.debug(
                    "%s apply skipped on %s: %s", what, self._host, err
                )
        _LOGGER.info("%s set on %s: %s", what, self._host, values)

    async def set_wifi_config(self, section: str, values: dict[str, str]) -> None:
        """Write WiFi fields for a band and apply.

        ``section`` is "2G" or "5G"; ``values`` e.g. {"Enable": "0"} or
        {"TxPower": "50"}. Changing WiFi will briefly disrupt wireless
        clients.
        """
        await self._set_and_apply("wificfg", section, values, f"WiFi {section}")

    async def get_led_config(self) -> str | None:
        """Read the front-panel LED state from uci.

        Returns the raw ``ledoff`` value: "0" = LEDs on, "1" = LEDs off,
        or ``None`` if unavailable.
        """
        resp = await self.call(
            "uci",
            "get",
            {"config": "system", "section": "@system[0]", "option": "ledoff"},
        )
        return resp.get("value") if isinstance(resp, dict) else None

    async def set_led(self, on: bool) -> None:
        """Turn the front-panel indicator LEDs on or off.

        Inverts to the firmware's ``ledoff`` flag (0=on, 1=off). Uses a
        single-field ``values`` payload so the surrounding ``system`` section
        (hostname, timezone, credentials, ...) is never touched.
        """
        await self._set_and_apply(
            "system", "@system[0]", {"ledoff": "0" if on else "1"}, "LED"
        )

    async def reboot(self) -> None:
        """system.reboot - restart the router (will drop connection ~60s)."""
        try:
            await self.call(*UBUS_REBOOT, retry=False)
        except NetisError:
            # reboot tears down the session; a connection drop is expected
            _LOGGER.info("Reboot issued to %s", self._host)

    async def send_sms(self, phone: str, message: str) -> None:
        """Send an SMS via the router's LTE modem (lte_ubus.lte_sendmsg).

        Only works on LTE-capable models with a SIM card inserted. The
        message text is sent as-is; the firmware handles encoding.
        """
        await self.call(
            "lte_ubus",
            "lte_sendmsg",
            {"phone": phone, "msg": message},
        )
        _LOGGER.info("SMS sent to %s via %s", phone, self._host)

    async def set_speed_limit(
        self, mac: str, down_speed: int = 0, up_speed: int = 0
    ) -> None:
        """Set per-device speed limit (devices_app.set_speed_limit).

        ``mac`` is the device MAC (uppercased internally). Speed values are
        in Kbps; 0 means unlimited (removes the limit).
        """
        await self.call(
            "devices_app",
            "set_speed_limit",
            {
                "mac": mac.upper(),
                "lt_enable": "1" if (down_speed or up_speed) else "0",
                "lt_down": str(down_speed),
                "lt_up": str(up_speed),
            },
        )
        _LOGGER.info(
            "Speed limit set for %s on %s: down=%d up=%d Kbps",
            mac, self._host, down_speed, up_speed,
        )

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------
    @staticmethod
    def _to_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @classmethod
    def parse(
        cls,
        info: dict,
        hosts: dict,
        mwan: dict,
        lte: dict,
        wifi: dict | None = None,
        ledoff: str | None = None,
    ) -> NetisData:
        """Convert raw ubus payloads into a typed snapshot."""
        values = hosts.get("values") if hosts else None
        raw_hosts = (hosts or {}).get("hosts") or values or []

        devices: list[NetisDevice] = []
        for entry in raw_hosts:
            mac = (entry.get("mac") or "").upper()
            if not mac:
                continue
            devices.append(
                NetisDevice(
                    mac=mac,
                    name=entry.get("alias") or None,
                    ip=entry.get("ip") or None,
                    online=bool(entry.get("online")),
                    wired=bool(entry.get("wire")),
                    wifi_24g=bool(entry.get("is_wifi")),
                    wifi_5g=bool(entry.get("is_5g")),
                    guest=bool(entry.get("is_guest")),
                    up_speed=cls._to_int(entry.get("up_speed")) or 0,
                    down_speed=cls._to_int(entry.get("down_speed")) or 0,
                    up_bytes=cls._to_int(entry.get("up_bytes")) or 0,
                    down_bytes=cls._to_int(entry.get("down_bytes")) or 0,
                    connected_seconds=cls._to_int(entry.get("second")) or 0,
                )
            )

        interfaces = (mwan or {}).get("interfaces") or {}
        wan_online = any(
            iface.get("status") == "online" for iface in interfaces.values()
        )

        lte_data = lte or {}
        lte_connected = cls._to_int(lte_data.get("lte_connect"))
        lte_connected = lte_connected == 1 if lte_connected is not None else None

        # WiFi: uci.get wificfg returns {values: {"2G": {...}, "5G": {...}}}
        wifi_values = ((wifi or {}).get("values")) or {}
        wifi_enabled: dict[str, bool | None] = {}
        wifi_txpower: dict[str, str | None] = {}
        for band in ("2G", "5G"):
            band_cfg = wifi_values.get(band) or {}
            enable = band_cfg.get("Enable")
            wifi_enabled[band] = (
                str(enable) == "1" if enable is not None else None
            )
            wifi_txpower[band] = band_cfg.get("TxPower")

        # LED: firmware flag ledoff -> 0 = on, 1 = off (inverted)
        led_on = str(ledoff) == "0" if ledoff is not None else None

        return NetisData(
            model=info.get("model"),
            firmware=info.get("version"),
            hardware_version=info.get("hd_version"),
            uptime=cls._to_int(info.get("uptime")),
            wan_in_speed=cls._to_int(info.get("all_in_byte_speed")),
            wan_out_speed=cls._to_int(info.get("all_out_byte_speed")),
            wan_in_bytes=cls._to_int(info.get("all_in_byte")),
            wan_out_bytes=cls._to_int(info.get("all_out_byte")),
            wan_online=wan_online,
            wan_interfaces={
                name: iface.get("status") for name, iface in interfaces.items()
            },
            ports=info.get("link_info") or [],
            lte_connected=lte_connected,
            lte_rsrp=cls._to_float(lte_data.get("lte_rsrp")),
            lte_rsrq=cls._to_float(lte_data.get("lte_rsrq")),
            lte_rssi=cls._to_float(lte_data.get("lte_rssi")),
            lte_mode=lte_data.get("lte_mode"),
            lte_isp=lte_data.get("lte_isp"),
            lte_ip=lte_data.get("lte_ip"),
            lte_imei=lte_data.get("imei"),
            wifi_enabled=wifi_enabled,
            wifi_txpower=wifi_txpower,
            led_on=led_on,
            devices=devices,
        )

    async def gather(self) -> NetisData:
        """Fetch all endpoints concurrently and return a typed snapshot."""
        info, hosts, mwan, lte, wifi, ledoff = await asyncio.gather(
            self.get_system_info(),
            self.get_hosts(),
            self.get_wan_status(),
            self.get_lte_info(),
            self.get_wifi_config(),
            self.get_led_config(),
            return_exceptions=True,
        )
        # LTE is optional (not every model is a 4G router): tolerate failure.
        if isinstance(lte, NetisError):
            _LOGGER.debug("LTE info unavailable: %s", lte)
            lte = {}
        if isinstance(wifi, NetisError):
            _LOGGER.debug("WiFi config unavailable: %s", wifi)
            wifi = {}
        if isinstance(ledoff, NetisError):
            _LOGGER.debug("LED state unavailable: %s", ledoff)
            ledoff = None
        if isinstance(info, NetisError):
            raise info
        if isinstance(hosts, NetisError):
            raise hosts
        if isinstance(mwan, NetisError):
            raise mwan
        return self.parse(info, hosts, mwan, lte, wifi, ledoff)
