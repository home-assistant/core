"""Support for recording a WebRTC camera stream using aiortc."""

import asyncio
from collections.abc import Callable
import concurrent.futures
import contextlib
import logging
from pathlib import Path
import threading
from typing import TYPE_CHECKING

from aiortc import (
    MediaStreamTrack,
    RTCConfiguration,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
)
from aiortc.contrib.media import MediaRecorder
from aiortc.sdp import candidate_from_sdp
import webrtc_models

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.ulid import ulid

from .webrtc import (
    WebRTCAnswer,
    WebRTCCandidate,
    WebRTCClientConfiguration,
    WebRTCError,
    WebRTCMessage,
    WebRTCSendMessage,
)

if TYPE_CHECKING:
    from . import Camera

_LOGGER = logging.getLogger(__name__)

_CONNECT_TIMEOUT = 20

DATA_ACTIVE_WEBRTC_RECORDING_ENTITIES: HassKey[set[str]] = HassKey(
    "camera_active_webrtc_recording_entities"
)


async def _add_ice_candidate(pc: RTCPeerConnection, message: WebRTCCandidate) -> None:
    """Add a camera ICE candidate to the peer connection."""
    candidate_init = message.candidate
    candidate_sdp = candidate_init.candidate
    if not candidate_sdp:
        await pc.addIceCandidate(None)
        return
    candidate = candidate_from_sdp(candidate_sdp.removeprefix("candidate:"))
    if isinstance(candidate_init, webrtc_models.RTCIceCandidateInit):
        candidate.sdpMid = candidate_init.sdp_mid
        candidate.sdpMLineIndex = candidate_init.sdp_m_line_index
    await pc.addIceCandidate(candidate)


def _configure_connection(
    client_config: WebRTCClientConfiguration,
) -> RTCPeerConnection:
    """Configure a RTCPeerConnection based on client configuration provided by the camera.

    Must be called from the worker thread since RTCPeerConnection remembers the current event loop.
    """

    pc = RTCPeerConnection(
        # Translate webrtc_models.RTCConfiguration to aiortc.RTCConfiguration
        configuration=RTCConfiguration(
            iceServers=[
                RTCIceServer(
                    urls=server.urls,
                    username=server.username,
                    credential=server.credential,
                )
                for server in client_config.configuration.ice_servers
            ]
        )
    )

    pc.addTransceiver("audio", direction="recvonly")
    pc.addTransceiver("video", direction="recvonly")
    if client_config.data_channel:
        pc.createDataChannel(client_config.data_channel)

    return pc


class _WebRTCRecorderCancelledError(BaseException):
    """Used to implement _WebRTCRecorder.cancel_threadsafe.

    asyncio.CancelledError cannot be used because it will not propagate cancellation to other tasks in the TaskGroup.
    """


class _WebRTCRecorder:
    """Manage a task running a WebRTC camera recording session.

    This task must be run in its own asyncio event loop on a worker thread. asyncio.MediaRecorder
    uses an async API, but also performs I/O operations that block the loop.
    """

    def __init__(
        self,
        *,
        entity_id: str,
        video_path: str,
        duration: float,
        client_config: WebRTCClientConfiguration,
        handle_async_webrtc_offer_threadsafe: Callable[
            [str, WebRTCSendMessage], concurrent.futures.Future[None]
        ],
        close_webrtc_session_threadsafe: Callable[[], concurrent.futures.Future[None]],
    ) -> None:
        """Initialize a recording session. Must be called in the same thread & event loop as the record() method."""
        self._entity_id = entity_id
        self._output = Path(video_path)
        self._duration = duration
        self._client_config = client_config
        self._session_id = ulid()
        self._handle_async_webrtc_offer_threadsafe = (
            handle_async_webrtc_offer_threadsafe
        )
        self._close_webrtc_session_threadsafe = close_webrtc_session_threadsafe
        self._recorder: MediaRecorder | None = None
        self._video_track: MediaStreamTrack | None = None
        self._audio_track: MediaStreamTrack | None = None

        self._pc = _configure_connection(self._client_config)
        self._pc.on("connectionstatechange", self._on_connection_state_change)
        self._pc.on("track", self._on_track)

        self._connected = asyncio.Event()
        """Set when the connection state changes to 'connected'"""

        self._loop = asyncio.get_running_loop()
        self._failure: asyncio.Future[None] = self._loop.create_future()
        """Future used to interrupt recording when a failure occurs"""

        self._messages: asyncio.Queue[WebRTCMessage] = asyncio.Queue()
        self._cleaning_up = False

    def cancel_threadsafe(self) -> None:
        """Request cancellation of the thread. Cancellation is not immediate and the thread should still be joined."""
        with contextlib.suppress(RuntimeError):
            self._loop.call_soon_threadsafe(
                self._set_failure, _WebRTCRecorderCancelledError()
            )

    def _set_failure(self, error: BaseException) -> None:
        """Raise an exception and stop the recording."""
        if not isinstance(error, _WebRTCRecorderCancelledError):
            _LOGGER.error("Failure during recording: %s", error, stack_info=True)
        if not self._failure.done():
            self._failure.set_exception(error)

    async def _raise_for_failure(self) -> None:
        """Raises an exception if _set_failure is called, cancelling the outer TaskGroup."""
        await self._failure

    async def record(self) -> None:
        """Negotiate and record the camera stream."""
        try:
            self._output.parent.mkdir(parents=True, exist_ok=True)
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._raise_for_failure())
                tg.create_task(self._async_consume_messages())
                await self._async_establish_connection()
                await self._async_start_recording()
                await asyncio.sleep(self._duration)
                _LOGGER.debug(
                    "Recording finished for %s, shutting down gracefully",
                    self._entity_id,
                )
                # Allow the two concurrent tasks to shut down cleanly
                self._messages.shutdown(immediate=True)
                self._failure.set_result(None)
        except* _WebRTCRecorderCancelledError:
            _LOGGER.debug("Recording cancelled for %s", self._entity_id)
        except* HomeAssistantError as group:
            # Choose the first HomeAssistantError as the one to raise
            error: Exception = group
            while isinstance(error, ExceptionGroup):
                error = error.exceptions[0]
            raise error from group
        except* Exception:
            _LOGGER.exception("Error during WebRTC recording for %s", self._entity_id)
            raise
        finally:
            try:
                await self._async_shutdown()
            except Exception:
                _LOGGER.exception(
                    "Error cleaning up WebRTC recording for %s",
                    self._entity_id,
                )
                raise

    async def _async_establish_connection(self) -> None:
        """Start the WebRTC connection by sending an offer and waiting for the connection state to become "connected"."""
        try:
            async with asyncio.timeout(_CONNECT_TIMEOUT):
                await self._pc.setLocalDescription(await self._pc.createOffer())
                await asyncio.wrap_future(
                    self._handle_async_webrtc_offer_threadsafe(
                        self._pc.localDescription.sdp,
                        self._on_message_threadsafe,
                    )
                )
                await self._connected.wait()
        except TimeoutError as err:
            raise HomeAssistantError(
                f"WebRTC connection not established within {_CONNECT_TIMEOUT} seconds"
            ) from err

    async def _async_consume_messages(self) -> None:
        """Process WebRTC signaling messages from the camera."""
        pending_candidates: list[WebRTCCandidate] = []
        received_answer = False
        while True:
            try:
                message = await self._messages.get()
            except asyncio.QueueShutDown:
                return

            if isinstance(message, WebRTCError):
                raise HomeAssistantError(
                    f"Received WebRTC error code {message.code} from {self._entity_id}: {message.message}"
                )

            if isinstance(message, WebRTCCandidate):
                if not received_answer:
                    pending_candidates.append(message)
                else:
                    await _add_ice_candidate(self._pc, message)

            elif isinstance(message, WebRTCAnswer):
                await self._pc.setRemoteDescription(
                    RTCSessionDescription(sdp=message.answer, type="answer")
                )
                for candidate in pending_candidates:
                    await _add_ice_candidate(self._pc, candidate)
                pending_candidates.clear()
                received_answer = True

    async def _async_start_recording(self) -> None:
        """Start the recorder for the specified duration."""
        assert self._recorder is None
        if self._video_track is None:
            raise HomeAssistantError(
                "WebRTC recorder established a connection without negotiating a video track"
            )
        self._recorder = MediaRecorder(str(self._output))

        self._recorder.addTrack(self._video_track)
        if self._audio_track is not None:
            self._recorder.addTrack(self._audio_track)

        await self._recorder.start()

    async def _on_connection_state_change(self) -> None:
        _LOGGER.debug("Connection state changed to: %s", self._pc.connectionState)
        if self._pc.connectionState == "connected":
            self._connected.set()
        elif (
            self._pc.connectionState in ("failed", "closed", "disconnected")
            and not self._cleaning_up
        ):
            self._set_failure(
                HomeAssistantError(
                    f"WebRTC connection {self._pc.connectionState} before recording finished"
                )
            )

    def _on_track(self, track: MediaStreamTrack) -> None:
        _LOGGER.debug("Received %s track", track.kind)
        if track.kind == "video":
            if self._video_track is not None:
                self._set_failure(
                    HomeAssistantError("WebRTC answer included multiple video tracks")
                )
                return
            self._video_track = track
        elif track.kind == "audio":
            if self._audio_track is not None:
                self._set_failure(
                    HomeAssistantError("WebRTC answer included multiple audio tracks")
                )
                return
            self._audio_track = track

    def _on_message_threadsafe(self, message: WebRTCMessage) -> None:
        if self._cleaning_up:
            return
        self._loop.call_soon_threadsafe(self._on_message, message)

    def _on_message(self, message: WebRTCMessage) -> None:
        _LOGGER.debug("Received signaling message: %s", message)
        self._messages.put_nowait(message)

    async def _async_shutdown(self) -> None:
        """Clean up all resources owned by the recording session."""
        self._cleaning_up = True
        errors: list[Exception] = []

        if self._recorder is not None:
            try:
                await self._recorder.stop()
            except Exception as err:  # noqa: BLE001
                errors.append(err)

        try:
            await self._pc.close()
        except Exception as err:  # noqa: BLE001
            errors.append(err)

        try:
            await asyncio.wrap_future(self._close_webrtc_session_threadsafe())
        except Exception as err:  # noqa: BLE001
            errors.append(err)

        if errors:
            raise ExceptionGroup(
                f"Error shutting down WebRTC recording for {self._entity_id}",
                errors,
            )


class _WebRTCRecorderRunner:
    """Manage an event loop for a _WebRTCRecorder."""

    def __init__(
        self,
        *,
        entity_id: str,
        video_path: str,
        duration: float,
        client_config: WebRTCClientConfiguration,
        handle_async_webrtc_offer_threadsafe: Callable[
            [str, WebRTCSendMessage], concurrent.futures.Future[None]
        ],
        close_webrtc_session_threadsafe: Callable[[], concurrent.futures.Future[None]],
    ) -> None:
        self._entity_id = entity_id
        self._video_path = video_path
        self._duration = duration
        self._client_config = client_config
        self._handle_async_webrtc_offer_threadsafe = (
            handle_async_webrtc_offer_threadsafe
        )
        self._close_webrtc_session_threadsafe = close_webrtc_session_threadsafe

        self._recorder_initialized = concurrent.futures.Future[_WebRTCRecorder]()
        self._cancelled = threading.Event()

    def run(self) -> None:
        """Run the recorder. This starts a new asyncio loop and must be run in a worker thread."""
        _LOGGER.debug("Recorder loop starting for %s", self._entity_id)
        try:
            asyncio.run(self._run())
        finally:
            _LOGGER.debug("Recorder loop exiting for %s", self._entity_id)

    async def _run(self) -> None:
        recorder = _WebRTCRecorder(
            entity_id=self._entity_id,
            video_path=self._video_path,
            duration=self._duration,
            client_config=self._client_config,
            handle_async_webrtc_offer_threadsafe=self._handle_async_webrtc_offer_threadsafe,
            close_webrtc_session_threadsafe=self._close_webrtc_session_threadsafe,
        )
        self._recorder_initialized.set_result(recorder)
        if self._cancelled.is_set():
            raise asyncio.CancelledError
        await recorder.record()

    def cancel_threadsafe(self) -> None:
        self._cancelled.set()
        if not self._recorder_initialized.done():
            return
        recorder = self._recorder_initialized.result()
        recorder.cancel_threadsafe()


async def async_record_webrtc(camera: Camera, video_path: str, duration: float) -> None:
    """Start a WebRTC stream from the camera and record it to a file for the specified duration."""
    # Check for file access
    if not camera.hass.config.is_allowed_path(video_path):
        raise HomeAssistantError(f"Can't write {video_path}, no access to path!")

    entity_id = camera.entity_id
    active_recording_entities = camera.hass.data.setdefault(
        DATA_ACTIVE_WEBRTC_RECORDING_ENTITIES, set()
    )
    if entity_id in active_recording_entities:
        raise HomeAssistantError(f"{entity_id} is already recording")

    active_recording_entities.add(entity_id)
    try:
        main_loop = camera.hass.loop
        session_id = ulid()

        def _handle_async_webrtc_offer_threadsafe(
            offer_sdp: str,
            send_message_threadsafe: WebRTCSendMessage,
        ) -> concurrent.futures.Future[None]:
            return asyncio.run_coroutine_threadsafe(
                camera.async_handle_async_webrtc_offer(
                    offer_sdp, session_id, send_message_threadsafe
                ),
                main_loop,
            )

        def _close_webrtc_session_threadsafe() -> concurrent.futures.Future[None]:
            return run_callback_threadsafe(
                main_loop, camera.close_webrtc_session, session_id
            )

        client_config = camera.async_get_webrtc_client_configuration()
        runner = _WebRTCRecorderRunner(
            entity_id=entity_id,
            video_path=video_path,
            duration=duration,
            client_config=client_config,
            handle_async_webrtc_offer_threadsafe=_handle_async_webrtc_offer_threadsafe,
            close_webrtc_session_threadsafe=_close_webrtc_session_threadsafe,
        )
        try:
            record_future = camera.hass.async_add_executor_job(runner.run)
            # Shield the future from cancellation so we can explicitly forward the cancellation to
            # the recorder and join its thread.
            await asyncio.shield(record_future)
        except asyncio.CancelledError:
            runner.cancel_threadsafe()
            await record_future
            raise
    finally:
        active_recording_entities.discard(entity_id)
        if not active_recording_entities:
            camera.hass.data.pop(DATA_ACTIVE_WEBRTC_RECORDING_ENTITIES, None)
