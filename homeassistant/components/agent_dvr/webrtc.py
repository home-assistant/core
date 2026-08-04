"""WebRTC data-channel client for Agent DVR's recordings/media API.

Agent DVR has no REST endpoint for browsing or downloading recordings.
Its own web frontend fetches them over a WebRTC DataChannel, negotiated
via a proprietary long-polling signaling channel (cmd.json/poll.json for
local connections). None of this is documented by the vendor; every
message shape used below was reverse-engineered from the server's own
frontend bundle (monitor.min.js) and verified live against a production
Agent DVR 7.8.0.0 server. See the PR description / docs/reverse-engineering
notes for how each piece was found and verified.

This module intentionally does not try to be a general WebRTC/Agent DVR
client: it implements exactly the operations this integration needs
(list/download recordings, continuous PTZ move, preset management).
"""

import asyncio
from collections.abc import Awaitable, Callable
import json
import logging
import random
import time
from typing import Any, Self, TypeVar
from urllib.parse import quote
import uuid

import aiohttp
from aiortc import (
    RTCConfiguration,
    RTCDataChannel,
    RTCIceCandidate,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
)

_LOGGER = logging.getLogger(__name__)

CONNECT_TIMEOUT = 20
DOWNLOAD_TIMEOUT = 90
POLL_INTERVAL = 0.1


class AgentDVRWebRTCError(Exception):
    """Raised when the WebRTC session fails to connect or a command fails."""


def _parse_ice_candidate(
    sdp: str, sdp_mline_index: int | None, sdp_mid: str | None
) -> RTCIceCandidate:
    """Parse a raw 'candidate:...' SDP line as sent by Agent DVR's signaling."""
    parts = sdp.replace("candidate:", "").split()
    return RTCIceCandidate(
        foundation=parts[0],
        component=int(parts[1]),
        protocol=parts[2],
        priority=int(parts[3]),
        ip=parts[4],
        port=int(parts[5]),
        type=parts[7],
        sdpMLineIndex=sdp_mline_index,
        sdpMid=sdp_mid,
    )


class AgentDVRWebRTCSession:
    """One-shot WebRTC session: connect, issue commands/downloads, close.

    Meant to be used as a short-lived async context manager for a single
    browse or download operation, not kept open indefinitely.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        use_ssl: bool = False,
    ) -> None:
        """Initialize the session (does not connect yet, see connect())."""
        self._http = session
        scheme = "https" if use_ssl else "http"
        self._base_url = f"{scheme}://{host}:{port}"
        self._auth = aiohttp.BasicAuth(username, password or "") if username else None
        self._pc: RTCPeerConnection | None = None
        self._channel: RTCDataChannel | None = None
        self._local_id = str(random.random())
        self._session_id = str(uuid.uuid4())
        self._login: dict[str, Any] = {}
        self._has_remote_description = False
        self._local_candidates: list[dict] = []
        self._recv_buffers: dict[str, list[str]] = {}
        self._pending: dict[str, asyncio.Future] = {}
        self._poll_task: asyncio.Task | None = None
        self._background_tasks: set[asyncio.Task] = set()

    async def __aenter__(self) -> Self:
        """Connect on entering the context manager."""
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Close on exiting the context manager."""
        await self.close()

    async def connect(self) -> None:
        """Bootstrap the session and negotiate the WebRTC data channel."""
        async with self._http.get(
            f"{self._base_url}/login.json?r={random.random()}", auth=self._auth
        ) as resp:
            if resp.status == 401:
                raise AgentDVRWebRTCError("Authentication failed (Protect API)")
            self._login = await resp.json()

        ice_servers = [
            RTCIceServer(
                urls=s["urls"],
                username=s.get("username"),
                credential=s.get("credential"),
            )
            for s in self._login["ICE"]["iceServers"]
        ]
        self._pc = RTCPeerConnection(
            configuration=RTCConfiguration(iceServers=ice_servers)
        )
        self._pc.on("icecandidate", self._on_icecandidate)

        self._channel = self._pc.createDataChannel("serverdata", ordered=True)
        self._channel.on("message", self._on_channel_message)
        channel_open = asyncio.Event()
        self._channel.on("open", channel_open.set)

        offer = await self._pc.createOffer()
        await self._pc.setLocalDescription(offer)

        scheme = self._base_url.split(":", 1)[0]
        await self._send_relay(
            {
                "command": "offer",
                "turn": "",
                "desc": {
                    "type": self._pc.localDescription.type,
                    "sdp": self._pc.localDescription.sdp,
                },
                "maxWidth": 1920,
                "maxHeight": 1080,
                "maxH264Profile": "42e028",
                "IceConfig": self._login["ICE"]["iceServers"],
                "SID": self._login["SID"],
                "Protocol": f"{scheme}:",
                "username": self._login.get("Username"),
                "accessMask": (self._login.get("Permissions") or {}).get("accessMask")
                or None,
            }
        )

        self._poll_task = asyncio.create_task(self._poll_loop())

        try:
            await asyncio.wait_for(channel_open.wait(), timeout=CONNECT_TIMEOUT)
        except TimeoutError as err:
            await self.close()
            raise AgentDVRWebRTCError(
                "Timed out establishing WebRTC data channel"
            ) from err

        await self.command("loadAPI")

    async def close(self) -> None:
        """Stop polling and tear down the RTCPeerConnection."""
        if self._poll_task:
            self._poll_task.cancel()
            self._poll_task = None
        if self._pc:
            await self._pc.close()
            self._pc = None

    async def _send_relay(self, payload: dict) -> None:
        payload = {
            "connectionID": "local",
            "sessionID": self._session_id,
            "action": "relay",
            **payload,
        }
        url = f"{self._base_url}/cmd.json?id={self._local_id}&userIdent={self._login['UserIdent']}&r={random.random()}"
        async with self._http.post(url, json=payload, auth=self._auth) as resp:
            await resp.read()

    def _on_icecandidate(self, candidate: Any) -> None:
        if candidate is None:
            return
        cand_payload = {
            "candidate": candidate.candidate
            if isinstance(candidate.candidate, str)
            else candidate
        }
        if self._has_remote_description:
            task = asyncio.ensure_future(
                self._send_relay(
                    {"command": "onicecandidate", "candidate": cand_payload}
                )
            )
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
        else:
            self._local_candidates.append(cand_payload)

    async def _poll_loop(self) -> None:
        while True:
            url = f"{self._base_url}/poll.json?id={self._local_id}&r={random.random()}"
            try:
                async with self._http.get(
                    url, auth=self._auth, timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    text = await resp.text()
            except TimeoutError, aiohttp.ClientError:
                await asyncio.sleep(POLL_INTERVAL)
                continue
            if text and text != '""':
                try:
                    msg = json.loads(text)
                except json.JSONDecodeError:
                    msg = None
                if isinstance(msg, dict):
                    await self._handle_relay_message(msg)
            await asyncio.sleep(POLL_INTERVAL)

    async def _handle_relay_message(self, e: dict) -> None:
        assert self._pc is not None
        cmd = e.get("command")
        if cmd == "OnSuccessAnswer":
            await self._pc.setRemoteDescription(
                RTCSessionDescription(sdp=e["sdp"], type="answer")
            )
            self._has_remote_description = True
            for cand in self._local_candidates:
                await self._send_relay({"command": "onicecandidate", "candidate": cand})
            self._local_candidates = []
        elif cmd == "OnIceCandidate":
            candidate = _parse_ice_candidate(
                e["sdp"], e.get("sdp_mline_index"), e.get("sdp_mid")
            )
            await self._pc.addIceCandidate(candidate)
        elif cmd == "OnIceCandidates":
            for c in e.get("candidates", []):
                candidate = _parse_ice_candidate(
                    c["sdp"], c.get("sdp_mline_index"), c.get("sdp_mid")
                )
                await self._pc.addIceCandidate(candidate)
        elif cmd == "disconnect":
            _LOGGER.warning("Agent DVR hat die WebRTC-Sitzung beendet")

    def _on_channel_message(self, message: Any) -> None:
        # Framing mirrors the client's own sendChunked(): "<P|F><ident>_<data...>"
        text = (
            message if isinstance(message, str) else message.decode("utf-8", "replace")
        )
        flag, rest = text[0], text[1:]
        ident, _, chunk = rest.partition("_")
        self._recv_buffers.setdefault(ident, []).append(chunk)
        if flag == "F":
            full = "".join(self._recv_buffers.pop(ident))
            fut = self._pending.pop(ident, None)
            if fut and not fut.done():
                fut.set_result(full)

    async def command(
        self, cmd: str, oid: int = -1, ot_id: int = -1, timeout: float = 15
    ) -> Any:
        """Run a loadjson command over the serverdata channel, return its parsed response.

        Device-scoped commands (e.g. ptzcommand, getptzcommands) need the real
        oid/ot_id here — the server resolves the target device from these envelope
        fields, not just from query-string parameters in `cmd`. Commands that
        operate across devices (e.g. getevents, which takes its own `objects=`
        list) work fine with the default -1/-1.
        """
        assert self._channel is not None
        ident = str(uuid.uuid4())
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[ident] = fut
        msg = {
            "type": "loadjson",
            "ident": ident,
            "oid": oid,
            "ot": ot_id,  # codespell:ignore ot
            "handler": "json",
            "cmd": cmd,
            "lc": "en",
            "data": False,
        }
        self._channel.send("F" + ident + "_" + json.dumps(msg))
        try:
            raw = await asyncio.wait_for(fut, timeout=timeout)
        except TimeoutError as err:
            self._pending.pop(ident, None)
            raise AgentDVRWebRTCError(
                f"Timed out waiting for response to: {cmd[:60]}"
            ) from err
        outer = json.loads(raw)
        response = outer.get("response")
        return json.loads(response) if isinstance(response, str) else response

    # -- PTZ continuous move ------------------------------------------------
    # Verified live against Dom1 (ONVIF PTZ) with snapshot comparisons before/
    # after each pulse. "ispydir_9"/"ispydir_10" (zoom) confirmed from the
    # client's own VR-joystick handler code rather than by testing zoom live.
    # Directions 2/4/6/8 (diagonals) exist but are unused/unverified here.
    PTZ_LEFT = "1"
    PTZ_DOWN = "3"
    PTZ_RIGHT = "5"
    PTZ_UP = "7"
    PTZ_ZOOM_IN = "9"
    PTZ_ZOOM_OUT = "10"
    PTZ_STOP = "11"

    async def ptz_move(
        self, oid: int, ot_id: int, direction: str, speed: float = 1.0
    ) -> None:
        """Start a continuous PTZ move in one of the PTZ_* directions."""
        cmd = f"ptzcommand&field=ptz&speed={speed}&value=ispydir_{direction}"
        await self.command(cmd, oid=oid, ot_id=ot_id)

    async def ptz_stop(self, oid: int, ot_id: int) -> None:
        """Stop a continuous PTZ move started by ptz_move()."""
        await self.command(
            f"ptzcommand&field=ptz&value=ispydir_{self.PTZ_STOP}", oid=oid, ot_id=ot_id
        )

    async def get_recordings(self, oid: int, ot_id: int, limit: int = 50) -> list[dict]:
        """List recent recordings/photo-grab events for one device.

        Each event dict has (at least): fn (filename), sb (size bytes),
        d (duration seconds), tg (comma-separated tags), c (server-side
        sortable timestamp/ticks). Do not pass enddate=0 to mimic "give me
        everything up to now" — Agent DVR interprets that as "before Unix
        epoch zero" and returns nothing; the default (omitted) is correct.
        """
        cmd = f"getevents&limit={limit}&objects=|{oid},{ot_id}|"
        data = await self.command(cmd)
        return data.get("events", [])

    async def download_file(
        self, oid: int, ot_id: int, filename: str, timeout: float = DOWNLOAD_TIMEOUT
    ) -> bytes:
        """Download a recording/grab file, fully reassembled, over its own data channel."""
        assert self._pc is not None
        label = f"download_{int(time.time() * 1000)}"
        dl_channel = self._pc.createDataChannel(label, ordered=True)
        done: asyncio.Future = asyncio.get_event_loop().create_future()
        state: dict[str, Any] = {"size": None, "received": 0, "chunks": []}

        def on_open() -> None:
            req = {
                "type": "download",
                "filename": filename,
                "ot": ot_id,  # codespell:ignore ot
                "oid": oid,
            }
            dl_channel.send(json.dumps(req))

        def on_message(msg: Any) -> None:
            if state["size"] is None:
                info = json.loads(msg)
                state["size"] = int(info["size"])
                return
            data = msg if isinstance(msg, (bytes, bytearray)) else msg.encode("utf-8")
            state["chunks"].append(data)
            state["received"] += len(data)
            if state["received"] >= state["size"] and not done.done():
                done.set_result(b"".join(state["chunks"]))

        dl_channel.on("open", on_open)
        dl_channel.on("message", on_message)

        try:
            return await asyncio.wait_for(done, timeout=timeout)
        except TimeoutError as err:
            raise AgentDVRWebRTCError(f"Timed out downloading {filename}") from err
        finally:
            dl_channel.close()

    # -- PTZ preset management ----------------------------------------------
    # Found via the preset-management modal in the frontend bundle
    # (PresetsModal: goPreset/editPreset/storePreset/delPreset/addPreset).
    # ptzpresetcreate serves two purposes depending on whether `token` is
    # given: no token = create a brand-new preset at the current position;
    # with token = overwrite an existing preset's stored position ("store").
    # Verified live: creating a NEW preset on Dom1 (ONVIF) returned
    # {"actionResult":"error","message":"Not Supported"} — this camera's
    # ONVIF firmware only supports overwriting presets it already has, not
    # creating arbitrary new ones. "store" (overwrite) was not tested live
    # since it would irreversibly move a real, in-use preset's position.

    async def _ptz_action(self, oid: int, ot_id: int, cmd: str) -> dict:
        result = await self.command(cmd, oid=oid, ot_id=ot_id)
        if isinstance(result, dict) and result.get("actionResult") == "error":
            raise AgentDVRWebRTCError(result.get("message") or "PTZ action failed")
        return result if isinstance(result, dict) else {}

    async def ptz_preset_create(self, oid: int, ot_id: int, name: str) -> dict:
        """Create a brand-new preset at the camera's current position.

        Many ONVIF PTZ cameras (confirmed for Dom1) don't support this and
        raise AgentDVRWebRTCError("Not Supported") — use ptz_preset_store
        against an existing preset's token instead on those cameras.
        """
        return await self._ptz_action(oid, ot_id, f"ptzpresetcreate&name={quote(name)}")

    async def ptz_preset_store(
        self, oid: int, ot_id: int, token: str, name: str
    ) -> dict:
        """Overwrite an existing preset (by token) with the current position."""
        return await self._ptz_action(
            oid, ot_id, f"ptzpresetcreate&name={quote(name)}&token={quote(token)}"
        )

    async def ptz_preset_delete(self, oid: int, ot_id: int, token: str) -> dict:
        """Delete an existing preset by token."""
        return await self._ptz_action(
            oid, ot_id, f"ptzpresetdelete&value={quote(token)}"
        )


T = TypeVar("T")


class AgentDVRWebRTCPool:
    """Keeps one WebRTC session warm per config entry and reuses it.

    Opening a fresh WebRTC session (login + ICE/DTLS handshake) takes
    roughly 1-2 seconds. Without pooling, every single PTZ button press
    pays that cost before the camera even starts moving, which is the
    main reason raw PTZ control feels sluggish. This pool keeps the
    session open for IDLE_TIMEOUT seconds after the last use so a burst
    of button presses (or browsing recordings) is near-instant, then lets
    it go so the integration isn't holding a permanent connection open to
    the camera server indefinitely.
    """

    IDLE_TIMEOUT = 45

    def __init__(self, session_factory: Callable[[], AgentDVRWebRTCSession]) -> None:
        """Initialize the pool (no session is opened until first use)."""
        self._factory = session_factory
        self._session: AgentDVRWebRTCSession | None = None
        self._lock = asyncio.Lock()
        self._idle_task: asyncio.Task | None = None

    async def run(self, fn: Callable[[AgentDVRWebRTCSession], Awaitable[T]]) -> T:
        """Run `fn` against a live, pooled session.

        Drops the session on error so the next call reconnects fresh
        instead of retrying a broken session.
        """
        session = await self._acquire()
        try:
            return await fn(session)
        except AgentDVRWebRTCError:
            await self.close()
            raise

    async def _acquire(self) -> AgentDVRWebRTCSession:
        async with self._lock:
            self._cancel_idle_timer()
            if self._session is None:
                session = self._factory()
                await session.connect()
                self._session = session
            self._schedule_idle_close()
            return self._session

    def _schedule_idle_close(self) -> None:
        self._idle_task = asyncio.ensure_future(self._idle_close_after())

    async def _idle_close_after(self) -> None:
        try:
            await asyncio.sleep(self.IDLE_TIMEOUT)
        except asyncio.CancelledError:
            return
        async with self._lock:
            if self._session is not None:
                await self._session.close()
                self._session = None

    def _cancel_idle_timer(self) -> None:
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = None

    async def close(self) -> None:
        """Close the pooled session, if any is currently open."""
        async with self._lock:
            self._cancel_idle_timer()
            if self._session is not None:
                await self._session.close()
                self._session = None
