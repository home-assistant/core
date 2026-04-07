"""KVS WebRTC streaming session for the Ecovacs camera integration.

Implements the full KVS WebRTC viewer flow using aiortc:
  - RTCPeerConnection setup (MAX_BUNDLE, ECDSA, H264 High Profile)
  - SDP offer/answer exchange via KVS WebSocket signaling
  - SDP patching to match Chrome WebRTC behavior expected by the robot
  - Proactive RTCP REMB + PLI to break the robot video transmission deadlock
  - Frame capture: H264 frames decoded by aiortc/av are converted to JPEG
  - MQTT P2P signaling (videoOpened) integrated via KvsMqttListener

Audio mid=0 MUST precede video mid=1 (firmware requirement).
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import fractions
import io
import json
import logging
import ssl
import time as _time
from typing import TYPE_CHECKING, Any

import aiohttp
from aiortc import (
    RTCConfiguration,
    RTCIceServer,
    RTCPeerConnection,
    RTCRtpReceiver,
    RTCSessionDescription,
)
from aiortc.mediastreams import AudioStreamTrack, MediaStreamError
from aiortc.rtcconfiguration import RTCBundlePolicy
from aiortc.rtp import (
    RTCP_PSFB_APP,
    RtcpPsfbPacket,
    RtcpReceiverInfo,
    RtcpRrPacket,
    pack_remb_fci,
)
from aiortc.sdp import candidate_from_sdp
import av
import boto3

from .kvs_api import end_watch, get_ma_gw, send_video_opened
from .kvs_signaling import make_ice_msg, make_sdp_offer_msg, sign_wss_url

if TYPE_CHECKING:
    from aiohttp import ClientSession, ClientWebSocketResponse

    from homeassistant.core import HomeAssistant

    from .kvs_mqtt import KvsMqttListener

_LOGGER = logging.getLogger(__name__)

_AUDIO_SAMPLE_RATE = 48000
_AUDIO_PTIME = 0.020  # 20ms per frame
_AUDIO_SAMPLES = int(_AUDIO_PTIME * _AUDIO_SAMPLE_RATE)  # 960 samples

# H264 High Profile Level 3.1 — preferred codec profile for robot video streams
_H264_PROFILE_LEVEL_ID = "42e01f"

# Number of 200ms polls to wait for the robot to announce its video SSRC
_SSRC_WAIT_ATTEMPTS = 15

# REMB target bitrate sent to the robot to encourage it to push video
_REMB_BITRATE = 5_000_000  # 5 Mbps


class VoiceAudioTrack(AudioStreamTrack):
    """Silent audio track sent to the robot (audio mid=0, firmware requirement)."""

    kind = "audio"
    _TRACK_ID = "KvsAudioTrack"

    def __init__(self) -> None:
        """Initialize track with zero timestamp."""
        super().__init__()
        self._id = self._TRACK_ID
        self._start: float | None = None
        self._timestamp: int = 0

    async def recv(self) -> Any:
        """Return a silent PCM audio frame at the correct presentation timestamp."""
        if self.readyState != "live":
            raise MediaStreamError
        if self._start is None:
            self._start = _time.time()
        else:
            self._timestamp += _AUDIO_SAMPLES
            wait = self._start + (self._timestamp / _AUDIO_SAMPLE_RATE) - _time.time()
            if wait > 0:
                await asyncio.sleep(wait)

        frame = av.AudioFrame(format="s16", layout="mono", samples=_AUDIO_SAMPLES)
        frame.planes[0].update(bytes(_AUDIO_SAMPLES * 2))
        frame.pts = self._timestamp
        frame.sample_rate = _AUDIO_SAMPLE_RATE
        frame.time_base = fractions.Fraction(1, _AUDIO_SAMPLE_RATE)
        return frame


class KvsStreamSession:
    """Manages a single KVS WebRTC camera session.

    Call start() to connect and begin receiving frames.
    Call stop() to close the session.
    The latest decoded JPEG frame is available via latest_jpeg.
    """

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        http_session: ClientSession,
        token: str,
        user_id: str,
        user_resource: str,
        did: str,
        mid: str,
        res: str,
        kvs_creds: dict[str, str],
        region: str,
        channel_name: str,
        client_id: str,
        session_id: str,
        video_track_id: str,
        mqtt_listener: KvsMqttListener,
        country: str = "ww",
        ma_gw: str | None = None,
        on_first_frame: asyncio.Event | None = None,
    ) -> None:
        """Initialize the KVS stream session."""
        self._hass = hass
        self._http_session = http_session
        self._token = token
        self._user_id = user_id
        self._user_resource = user_resource
        self._did = did
        self._mid = mid
        self._res = res
        self._kvs_creds = kvs_creds
        self._region = region
        self._channel_name = channel_name
        self._client_id = client_id
        self._session_id = session_id
        self._video_track_id = video_track_id
        self._mqtt_listener = mqtt_listener
        self._country = country
        self._ma_gw = ma_gw if ma_gw is not None else get_ma_gw("ww")
        self._on_first_frame = on_first_frame

        self.latest_jpeg: bytes | None = None
        self._done = asyncio.Event()
        self._task: asyncio.Task | None = None

        # Per-run state — reset at the start of each _run_session call
        self._frame_count: int = 0
        self._robot_video_ssrc: int | None = None
        self._offer_sdp_str: str | None = None
        self._pc: RTCPeerConnection | None = None
        self._ice_queue: asyncio.Queue = asyncio.Queue()
        self._sent_candidates: set[str] = set()
        self._subtasks: list[asyncio.Task] = []

    def is_done(self) -> bool:
        """Return True if the session has finished."""
        return self._done.is_set()

    async def start(self) -> None:
        """Start the WebRTC session task."""
        self._done.clear()
        self._task = asyncio.create_task(self._run_with_retry())

    async def stop(self) -> None:
        """Stop the WebRTC session."""
        self._done.set()
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(self._task), timeout=5.0)
        self._task = None

    async def _run_with_retry(self) -> None:
        """Run the WebRTC session with up to 3 retry attempts on 0-frame failure."""
        kvs_creds = self._kvs_creds
        region = self._region
        channel_name = self._channel_name
        client_id = self._client_id
        session_id = self._session_id
        video_track_id = self._video_track_id

        for attempt in range(3):
            if self._done.is_set():
                break
            if attempt > 0:
                _LOGGER.info("KVS retry attempt %d/3", attempt + 1)
            try:
                frame_count = await self._run_session(
                    kvs_creds=kvs_creds,
                    region=region,
                    channel_name=channel_name,
                    client_id=client_id,
                    video_track_id=video_track_id,
                )
            except asyncio.CancelledError:
                break
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("KVS session error (attempt %d): %s", attempt + 1, err)
                frame_count = 0

            if frame_count > 0 or self._done.is_set():
                break

            # Refresh KVS credentials for the retry
            _LOGGER.debug("0 frames received — refreshing KVS session for retry")
            await end_watch(
                self._http_session,
                token=self._token,
                user_id=self._user_id,
                session_id=session_id,
                video_track_id=video_track_id,
                country=self._country,
                ma_gw=self._ma_gw,
            )

        if not self._done.is_set():
            self._done.set()

    async def _run_session(
        self,
        *,
        kvs_creds: dict[str, str],
        region: str,
        channel_name: str,
        client_id: str,
        video_track_id: str,
    ) -> int:
        """Execute a single WebRTC session and return the frame count received."""
        # Reset per-run state
        self._frame_count = 0
        self._robot_video_ssrc = None
        self._offer_sdp_str = None
        self._subtasks = []

        channel_arn, wss_ep, ice_servers_raw = await self._hass.async_add_executor_job(
            self._aws_sync_setup, channel_name, kvs_creds, region
        )
        _LOGGER.debug("KVS ARN=%s WSS=%s", channel_arn, wss_ep)

        pc = self._create_peer_connection(ice_servers_raw, region)
        self._pc = pc

        @pc.on("track")
        async def on_track(track: Any) -> None:
            _LOGGER.debug("Track received: kind=%s", track.kind)
            await self._handle_track(track)

        @pc.on("connectionstatechange")
        async def on_conn_state() -> None:
            await self._handle_conn_state(pc)

        @pc.on("iceconnectionstatechange")
        async def on_ice() -> None:
            await self._handle_ice_state()

        try:
            await self._run_signaling(wss_ep, channel_arn, client_id, kvs_creds, region)
        finally:
            if pc.connectionState != "closed":
                with contextlib.suppress(Exception):
                    await pc.close()
            # Cancel all internal subtasks (video/audio consumers, PLI loop, etc.) so
            # they do not outlive the session. Gather with return_exceptions so a single
            # CancelledError doesn't hide other cleanup failures.
            for task in self._subtasks:
                if not task.done():
                    task.cancel()
            if self._subtasks:
                await asyncio.gather(*self._subtasks, return_exceptions=True)
            self._subtasks = []

        return self._frame_count

    @staticmethod
    def _aws_sync_setup(
        channel_name: str,
        kvs_creds: dict[str, str],
        region: str,
    ) -> tuple[str, str, list]:
        """Perform blocking AWS KVS setup (called via executor).

        Returns (channel_arn, wss_endpoint, ice_servers_raw).
        """
        kvs_client = boto3.client(
            "kinesisvideo",
            region_name=region,
            aws_access_key_id=kvs_creds["AccessKeyId"],
            aws_secret_access_key=kvs_creds["SecretAccessKey"],
            aws_session_token=kvs_creds["SessionToken"],
        )
        desc = kvs_client.describe_signaling_channel(ChannelName=channel_name)
        channel_arn = desc["ChannelInfo"]["ChannelARN"]

        ep = kvs_client.get_signaling_channel_endpoint(
            ChannelARN=channel_arn,
            SingleMasterChannelEndpointConfiguration={
                "Protocols": ["WSS", "HTTPS"],
                "Role": "VIEWER",
            },
        )
        wss_ep = next(
            e["ResourceEndpoint"]
            for e in ep["ResourceEndpointList"]
            if e["Protocol"] == "WSS"
        )
        https_ep = next(
            e["ResourceEndpoint"]
            for e in ep["ResourceEndpointList"]
            if e["Protocol"] == "HTTPS"
        )

        sig_client = boto3.client(
            "kinesis-video-signaling",
            endpoint_url=https_ep,
            region_name=region,
            aws_access_key_id=kvs_creds["AccessKeyId"],
            aws_secret_access_key=kvs_creds["SecretAccessKey"],
            aws_session_token=kvs_creds["SessionToken"],
        )
        ice_resp = sig_client.get_ice_server_config(
            ChannelARN=channel_arn, ClientId="VIEWER"
        )

        ice_servers_raw = [
            {
                "urls": srv["Uris"],
                "username": srv.get("Username", ""),
                "credential": srv.get("Password", ""),
            }
            for srv in ice_resp["IceServerList"]
            if srv.get("Uris", [])
        ]

        return channel_arn, wss_ep, ice_servers_raw

    def _create_peer_connection(
        self, ice_servers_raw: list, region: str
    ) -> RTCPeerConnection:
        """Create and configure the RTCPeerConnection.

        Sets up ICE servers, stream ID, and H264 codec preferences.
        Transceiver order: audio mid=0 FIRST, video mid=1 SECOND (firmware requirement).
        """
        ice_servers = [
            RTCIceServer(urls=[f"stun:stun.kinesisvideo.{region}.amazonaws.com:443"])
        ]
        ice_servers.extend(
            RTCIceServer(
                urls=srv["urls"],
                username=srv["username"],
                credential=srv["credential"],
            )
            for srv in ice_servers_raw
        )

        pc = RTCPeerConnection(
            RTCConfiguration(
                iceServers=ice_servers,
                bundlePolicy=RTCBundlePolicy.MAX_BUNDLE,
            )
        )
        # The KVS robot firmware requires the SDP msid line to read
        # "KvsLocalMediaStream KvsAudioTrack". aiortc generates an internal
        # random stream ID; overriding it via name-mangled attribute is the
        # only way to control the msid without forking aiortc.
        # Pinned to aiortc==1.14.0 in manifest.json — re-validate on upgrades.
        pc._RTCPeerConnection__stream_id = "KvsLocalMediaStream"  # type: ignore[attr-defined]  # noqa: SLF001

        audio_track = VoiceAudioTrack()
        pc.addTransceiver(audio_track, direction="sendrecv")

        pc.addTransceiver("video", direction="recvonly")
        video_tr = next(t for t in pc.getTransceivers() if t.kind == "video")
        caps = RTCRtpReceiver.getCapabilities("video")
        h264 = [c for c in caps.codecs if c.mimeType == "video/H264"]
        h264.sort(
            key=lambda c: (
                0
                if c.parameters.get("profile-level-id") == _H264_PROFILE_LEVEL_ID
                else 1
            )
        )
        video_tr.setCodecPreferences(h264)

        return pc

    async def _handle_track(self, track: Any) -> None:
        """Dispatch incoming track to the appropriate consumer coroutine."""
        if track.kind == "video":
            task = asyncio.create_task(self._consume_video_track(track))
            self._subtasks.append(task)
        elif track.kind == "audio":
            task = asyncio.create_task(self._drain_audio_track(track))
            self._subtasks.append(task)

    async def _consume_video_track(self, track: Any) -> None:
        """Receive video frames and convert them to JPEG stored in latest_jpeg."""
        while not self._done.is_set():
            try:
                frame = await asyncio.wait_for(track.recv(), timeout=2.0)
            except TimeoutError:
                continue
            except Exception:  # noqa: BLE001
                break
            if self._frame_count == 0:
                _LOGGER.info(
                    "First video frame: pts=%s %sx%s",
                    frame.pts,
                    getattr(frame, "width", "?"),
                    getattr(frame, "height", "?"),
                )
                if self._on_first_frame is not None:
                    self._on_first_frame.set()
            self._frame_count += 1
            try:
                img = frame.to_image()
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=80)
                self.latest_jpeg = buf.getvalue()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Frame to JPEG error: %s", err)

    async def _drain_audio_track(self, track: Any) -> None:
        """Drain incoming audio frames (discarded — firmware compliance only)."""
        while not self._done.is_set():
            try:
                await asyncio.wait_for(track.recv(), timeout=2.0)
            except TimeoutError:
                continue
            except Exception:  # noqa: BLE001
                break

    async def _handle_conn_state(self, pc: RTCPeerConnection) -> None:
        """React to RTCPeerConnection state changes."""
        _LOGGER.info("WebRTC connectionState: %s", pc.connectionState)
        if pc.connectionState == "connected":
            video_tr = next(
                (t for t in pc.getTransceivers() if t.kind == "video"), None
            )
            task = asyncio.create_task(self._remb_pli_loop(video_tr))
            self._subtasks.append(task)
        elif pc.connectionState in ("failed", "closed", "disconnected"):
            self._done.set()

    async def _remb_pli_loop(self, video_tr: Any) -> None:
        """Send proactive RTCP REMB+PLI to break the robot video transmission deadlock."""
        if video_tr is None:
            return
        for _ in range(_SSRC_WAIT_ATTEMPTS):
            if self._robot_video_ssrc is not None:
                break
            await asyncio.sleep(0.2)
        if self._robot_video_ssrc is None:
            _LOGGER.warning("REMB/PLI: robot SSRC not available — skipping")
            return

        receiver = video_tr.receiver
        ssrc = self._robot_video_ssrc

        # Proactive RTCP RR: break robot's wait-for-RR deadlock
        try:
            rr = RtcpRrPacket(
                ssrc=video_tr.sender._ssrc,  # noqa: SLF001
                reports=[
                    RtcpReceiverInfo(
                        ssrc=ssrc,
                        fraction_lost=0,
                        packets_lost=0,
                        highest_sequence=0,
                        jitter=0,
                        lsr=0,
                        dlsr=0,
                    )
                ],
            )
            await receiver._send_rtcp(rr)  # noqa: SLF001
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("RTCP RR send error: %s", err)

        count = 0
        # Phase 1: aggressive REMB+PLI until the first decoded frame arrives.
        # Some robots (e.g. X5) delay sending the initial IDR frame; repeated PLI
        # breaks the deadlock.
        while not self._done.is_set() and self._frame_count == 0:
            try:
                remb = RtcpPsfbPacket(
                    fmt=RTCP_PSFB_APP,
                    ssrc=video_tr.sender._ssrc,  # noqa: SLF001
                    media_ssrc=0,
                    fci=pack_remb_fci(_REMB_BITRATE, [ssrc]),
                )
                await receiver._send_rtcp(remb)  # noqa: SLF001
                _LOGGER.debug("RTCP REMB #%d sent (5 Mbps)", count + 1)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("REMB send error: %s", err)

            try:
                await receiver._send_rtcp_pli(ssrc)  # noqa: SLF001
                count += 1
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("PLI send error: %s", err)
                break

            try:
                await asyncio.wait_for(self._done.wait(), timeout=2.0)
                break
            except TimeoutError:
                pass

        # Phase 2: periodic PLI every 10 s to help the H264 decoder recover from
        # NAL-unit parse errors caused by packet loss or robot firmware quirks.
        # Without periodic PLI the decoder may never receive a fresh SPS/PPS
        # (keyframe) and will drop all subsequent packets.
        _PLI_INTERVAL = 10.0
        while not self._done.is_set():
            try:
                await asyncio.wait_for(self._done.wait(), timeout=_PLI_INTERVAL)
                break
            except TimeoutError:
                pass
            if self._done.is_set():
                break
            try:
                await receiver._send_rtcp_pli(ssrc)  # noqa: SLF001
                _LOGGER.debug("Periodic PLI sent (frame_count=%d)", self._frame_count)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Periodic PLI send error: %s", err)
                break

    async def _handle_ice_state(self) -> None:
        """React to ICE connection state changes."""
        _LOGGER.info("ICE connectionState: %s", self._pc.iceConnectionState)
        if self._pc.iceConnectionState in ("connected", "completed"):
            task = asyncio.create_task(
                send_video_opened(
                    enqueue_publish=self._mqtt_listener.enqueue_publish,
                    token=self._token,
                    user_id=self._user_id,
                    user_resource=self._user_resource,
                    did=self._did,
                    mid=self._mid,
                    res=self._res,
                )
            )
            self._subtasks.append(task)

    async def _run_signaling(
        self,
        wss_ep: str,
        channel_arn: str,
        client_id: str,
        kvs_creds: dict[str, str],
        region: str,
    ) -> None:
        """Manage the KVS WebSocket signaling session (offer/answer + ICE)."""
        signed_url = sign_wss_url(wss_ep, channel_arn, client_id, kvs_creds, region)
        ssl_ctx = await self._hass.async_add_executor_job(ssl.create_default_context)
        self._ice_queue = asyncio.Queue()
        self._sent_candidates = set()

        @self._pc.on("icecandidate")
        def on_local_ice(candidate: Any) -> None:
            if candidate:
                self._ice_queue.put_nowait(candidate)

        async with self._http_session.ws_connect(
            signed_url,
            ssl=ssl_ctx,
            heartbeat=None,
            timeout=15,
        ) as ws:
            offer = await self._pc.createOffer()
            await self._pc.setLocalDescription(offer)
            self._offer_sdp_str = offer.sdp
            patched_sdp = _patch_sdp_offer(offer.sdp)
            await ws.send_str(make_sdp_offer_msg(patched_sdp, client_id))
            _LOGGER.info("SDP offer sent")
            await asyncio.gather(
                self._run_recv_loop(ws),
                self._run_ice_sender(ws, client_id),
                self._run_closer(ws),
            )

    async def _run_recv_loop(self, ws: ClientWebSocketResponse) -> None:
        """Receive and dispatch KVS signaling messages (SDP_ANSWER, ICE_CANDIDATE, GO_AWAY)."""
        while True:
            try:
                msg = await ws.receive()
            except Exception:  # noqa: BLE001
                break
            if msg.type in (
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.ERROR,
            ):
                break
            if msg.type != aiohttp.WSMsgType.TEXT:
                continue
            raw = msg.data
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("messageType", "")
            payload_b64 = msg.get("messagePayload", "")
            payload_str = ""
            if payload_b64:
                with contextlib.suppress(ValueError):
                    payload_str = base64.b64decode(payload_b64).decode(errors="replace")

            if msg_type == "SDP_ANSWER":
                await self._handle_sdp_answer(payload_str)
            elif msg_type == "ICE_CANDIDATE":
                await self._handle_ice_candidate(payload_str)
            elif msg_type == "GO_AWAY":
                _LOGGER.warning("GO_AWAY received — closing session")
                self._done.set()

    async def _handle_sdp_answer(self, payload_str: str) -> None:
        """Process an SDP_ANSWER message from the signaling channel."""
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError as err:
            _LOGGER.warning("SDP_ANSWER JSON error: %s", err)
            return
        answer_sdp_raw = payload.get("sdp", "")
        for line in answer_sdp_raw.splitlines():
            if line.startswith("a=ssrc:"):
                with contextlib.suppress(ValueError):
                    self._robot_video_ssrc = int(line.split(":")[1].split()[0])
                break
        answer_sdp = _check_sdp_answer(self._offer_sdp_str or "", answer_sdp_raw)
        try:
            await self._pc.setRemoteDescription(
                RTCSessionDescription(sdp=answer_sdp, type="answer")
            )
            _LOGGER.info("Remote description set")
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("SDP_ANSWER setRemoteDescription error: %s", err)

    async def _handle_ice_candidate(self, payload_str: str) -> None:
        """Process an ICE_CANDIDATE message from the signaling channel."""
        try:
            cand_data = json.loads(payload_str)
        except json.JSONDecodeError as err:
            _LOGGER.debug("ICE candidate JSON error: %s", err)
            return
        try:
            cand = candidate_from_sdp(cand_data["candidate"].split("candidate:", 1)[-1])
            cand.sdpMid = cand_data.get("sdpMid", "0")
            cand.sdpMLineIndex = cand_data.get("sdpMLineIndex", 0)
            await self._pc.addIceCandidate(cand)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("ICE candidate error: %s", err)

    async def _run_ice_sender(
        self, ws: ClientWebSocketResponse, client_id: str
    ) -> None:
        """Send local ICE candidates over the WebSocket signaling channel."""
        fallback = _parse_candidates_from_local_sdp(self._pc.localDescription.sdp)
        for cand_str, sdp_mid, sdp_mline_idx in fallback:
            if cand_str not in self._sent_candidates:
                self._sent_candidates.add(cand_str)
                await ws.send_str(
                    make_ice_msg(cand_str, sdp_mid, sdp_mline_idx, client_id)
                )

        while not self._done.is_set():
            try:
                c = await asyncio.wait_for(self._ice_queue.get(), timeout=1.0)
                if not c.candidate:
                    continue
                parts = c.candidate.split()
                if len(parts) > 2 and parts[2].lower() == "tcp":
                    continue
                if c.candidate in self._sent_candidates:
                    continue
                self._sent_candidates.add(c.candidate)
                await ws.send_str(
                    make_ice_msg(c.candidate, c.sdpMid, c.sdpMLineIndex, client_id)
                )
            except TimeoutError:
                pass
            except Exception:  # noqa: BLE001
                break

    async def _run_closer(self, ws: ClientWebSocketResponse) -> None:
        """Wait for the done event then force-close the WebSocket."""
        await self._done.wait()
        with contextlib.suppress(Exception):
            await ws.close()


# ── SDP helpers ───────────────────────────────────────────────────────────────


def _patch_sdp_offer(sdp: str) -> str:
    """Patch the aiortc SDP offer to match Chrome WebRTC behavior.

    Required changes:
    1. Remove a=ssrc and a=msid from the recvonly video section.
    2. Insert a=rtcp-rsize after a=rtcp-mux in the video section.
    3. Keep only the sha-256 fingerprint (remove sha-384, sha-512).
    """
    lines = sdp.splitlines()
    result = []
    in_video = False
    video_is_recvonly = False
    rtcp_rsize_added = False
    sha256_seen = False

    for line in lines:
        if line.startswith("m="):
            in_video = line.startswith("m=video")
            video_is_recvonly = False
            rtcp_rsize_added = False
            sha256_seen = False

        if line.startswith("a=fingerprint:"):
            algo = line.split(":")[1].split()[0] if ":" in line else ""
            if algo == "sha-256" and not sha256_seen:
                sha256_seen = True
                result.append(line)
            continue

        if in_video and line == "a=recvonly":
            video_is_recvonly = True

        if in_video and video_is_recvonly:
            if line.startswith(("a=ssrc:", "a=msid:")):
                continue
            if line == "a=rtcp-mux" and not rtcp_rsize_added:
                result.append(line)
                result.append("a=rtcp-rsize")
                rtcp_rsize_added = True
                continue

        result.append(line)

    return "\r\n".join(result) if "\r\n" in sdp else "\n".join(result)


def _check_sdp_answer(offer_sdp: str, answer_sdp: str) -> str:
    """Validate and normalize the SDP answer from the robot.

    Filters invalid ICE candidates (port=0, all-zero addresses) and reorders
    m= sections to match the offer if the robot returns them in wrong order.
    """
    _BAD_ADDRS = {
        "0000:0000:0000:0000:0000:0000:0000:0000",
        "0:0:0:0:0:0:0:0",
        "::",
        "0.0.0.0",
    }
    filtered = []
    for line in answer_sdp.splitlines(keepends=False):
        if line.startswith("a=candidate:"):
            parts = line.split()
            if len(parts) >= 6:
                addr = parts[4]
                try:
                    port_val = int(parts[5])
                except ValueError:
                    port_val = 1
                if port_val == 0 or addr in _BAD_ADDRS:
                    continue
        filtered.append(line)

    eol = "\r\n" if "\r\n" in answer_sdp else "\n"
    answer_sdp = eol.join(filtered)

    ov = offer_sdp.find("m=video")
    oa = offer_sdp.find("m=audio")
    av_ = answer_sdp.find("m=video")
    aa = answer_sdp.find("m=audio")
    if -1 in (ov, oa, av_, aa):
        return answer_sdp
    if (ov < oa) == (av_ < aa):
        return answer_sdp

    _LOGGER.warning("SDP answer m= order differs from offer — reordering")
    prefix = answer_sdp[: min(av_, aa)]
    first = answer_sdp[min(av_, aa) : max(av_, aa)]
    second = answer_sdp[max(av_, aa) :]
    return prefix + second + first


def _parse_candidates_from_local_sdp(sdp: str) -> list[tuple[str, str, int]]:
    """Extract ICE candidates from pc.localDescription.sdp (skip TCP, dedup)."""
    result: list[tuple[str, str, int]] = []
    seen: set[str] = set()
    current_mid: str | None = None
    current_mline_index: int = -1

    for line in sdp.splitlines():
        if line.startswith("m="):
            current_mline_index += 1
            current_mid = None
        elif line.startswith("a=mid:"):
            current_mid = line[len("a=mid:") :]
        elif line.startswith("a=candidate:") and current_mid is not None:
            cand_str = line[2:]
            parts = cand_str.split()
            if len(parts) > 2 and parts[2].lower() == "tcp":
                continue
            if cand_str not in seen:
                seen.add(cand_str)
                result.append((cand_str, current_mid, current_mline_index))

    return result
