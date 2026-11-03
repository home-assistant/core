"""Integration checks for opt-in Secure Video camera services."""

import asyncio
import shutil
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import uuid4

from pyhap.hap_handler import HAPStatusError
from pyhap.hap_session import HAPSession
import pytest

from homeassistant.components import camera, ffmpeg
from homeassistant.components.homekit.accessories import HomeBridge, HomeDriver
from homeassistant.components.homekit.const import (
    CONF_LINKED_MOTION_SENSOR,
    CONF_MAX_WIDTH,
    CONF_STREAM_SOURCE,
    SERV_MOTION_SENSOR,
)
from homeassistant.components.homekit.hksv_hardware import HardwareEncoder
from homeassistant.components.homekit.hksv_stream import MediaObservation
from homeassistant.components.homekit.type_cameras import FFMPEG_PID, Camera
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.mark.parametrize(
    ("setting", "expected"), [(None, True), (True, True), (False, False)]
)
async def test_receive_timestamps_source_setting(
    hass: HomeAssistant, run_driver: HomeDriver, setting: bool | None, expected: bool
) -> None:
    """Use receive timestamps by default while respecting per-camera choices."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    config = {} if setting is None else {"secure_video_receive_timestamps": setting}
    hass.states.async_set("camera.test", "idle")
    accessory = Camera(hass, run_driver, "Camera", "camera.test", 2, config)
    with patch(
        "homeassistant.components.homekit.type_cameras.SharedCameraStream.open",
        new_callable=AsyncMock,
    ) as open_stream:
        await accessory._async_get_hksv_source()
    open_stream.assert_awaited_once_with(
        hass, "camera.test", receive_timestamps=expected
    )


@pytest.mark.usefixtures("socket_enabled")
async def test_camera_motion_missing_at_start(hass: HomeAssistant, run_driver) -> None:
    """A configured motion entity may appear after the accessory starts."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    await async_setup_component(
        hass, camera.DOMAIN, {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    hass.states.async_set("camera.demo_camera", None)
    accessory = Camera(
        hass,
        run_driver,
        "Camera",
        "camera.demo_camera",
        2,
        {
            CONF_LINKED_MOTION_SENSOR: "binary_sensor.motion",
            "secure_video": True,
            "secure_video_native": True,
        },
    )
    bridge = HomeBridge("hass", run_driver, "Test Bridge")
    bridge.add_accessory(accessory)
    assert accessory._hksv is not None
    assert accessory._hksv.preserve_source is True
    assert accessory.get_service(SERV_MOTION_SENSOR)
    assert not accessory._hksv.snapshot_allowed(None)
    accessory.run()
    await hass.async_block_till_done()
    async with asyncio.timeout(2):
        while not accessory._hksv.ready:
            await asyncio.sleep(0.01)
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()
    assert accessory._char_motion_detected.value
    assert (
        accessory._hksv.services.transport
        in accessory._hksv.services.recording.linked_services
    )
    assert (
        accessory.get_service(SERV_MOTION_SENSOR)
        in accessory._hksv.services.recording.linked_services
    )
    assert accessory._hksv_motion_active.value is True
    assert len(accessory._hksv_stream_chars) == len(accessory._management)
    for char in accessory._hksv_stream_chars:
        assert char.value == 1
        assert accessory.iid_manager.get_iid(char) is not None
    session = HAPSession(uuid4(), b"x" * 32)
    first = accessory._hksv_stream_chars[0]
    first.client_update_value(0, session=session)
    assert not accessory._hksv.stream_active(0)
    with pytest.raises(RuntimeError, match="stream is disabled"):
        await accessory.start_stream({"id": "disabled", "stream_idx": 0}, {})
    first.client_update_value(1, session=session)
    assert accessory._hksv.stream_active(0)
    slot_zero = {"id": "slot_zero", "stream_idx": 0}
    slot_one = {"id": "slot_one", "stream_idx": 1}
    accessory.sessions.update({"slot_zero": slot_zero, "slot_one": slot_one})
    with patch.object(accessory, "stop_stream", new_callable=AsyncMock) as stop_stream:
        first.client_update_value(0, session=session)
        await hass.async_block_till_done()
        stop_stream.assert_awaited_once_with(slot_zero)
    first.client_update_value(1, session=session)
    accessory.sessions.clear()
    session_info = {"id": "existing"}
    accessory.sessions["existing"] = session_info
    session = HAPSession(uuid4(), b"x" * 32)
    with patch.object(accessory, "stop_stream", new_callable=AsyncMock) as stop_stream:
        accessory._hksv.services.camera_active.client_update_value(0, session=session)
        await hass.async_block_till_done()
        stop_stream.assert_awaited_once_with(session_info)
        assert accessory._hksv_motion_active.value is False
    accessory.sessions.clear()
    await accessory.stop()


async def test_insufficient_camera_limits_preserve_live_camera(
    hass: HomeAssistant, run_driver
) -> None:
    """Do not advertise recording when configured limits exclude its formats."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.demo_camera", "idle")
    accessory = Camera(
        hass,
        run_driver,
        "Camera",
        "camera.demo_camera",
        2,
        {
            CONF_LINKED_MOTION_SENSOR: "binary_sensor.motion",
            "secure_video": True,
            CONF_MAX_WIDTH: 1280,
        },
    )
    assert accessory._hksv is None
    assert accessory._management
    assert accessory.get_service(SERV_MOTION_SENSOR)


async def test_live_and_snapshot_available_while_hksv_probes(
    hass: HomeAssistant, run_driver
) -> None:
    """Allow existing camera access after privacy restore while probe is pending."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.demo_camera", "idle")
    accessory = Camera(
        hass,
        run_driver,
        "Camera",
        "camera.demo_camera",
        2,
        {CONF_LINKED_MOTION_SENSOR: "binary_sensor.motion", "secure_video": True},
    )
    controller = accessory._hksv
    assert controller is not None
    request = {"id": "test", "stream_idx": 0}
    with pytest.raises(RuntimeError, match="stream is disabled"):
        await accessory.start_stream(request, {})
    with pytest.raises(HAPStatusError):
        await accessory.async_get_snapshot({"image-width": 640, "image-height": 360})
    entered, release = asyncio.Event(), asyncio.Event()

    async def probe():
        entered.set()
        await release.wait()

    with (
        patch.object(controller.store, "async_load", new=AsyncMock(return_value={})),
        patch.object(controller, "_discover_native", new=probe),
        patch.object(controller.hds, "start", new=AsyncMock()),
        patch.object(
            accessory,
            "_async_get_hksv_source",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    image=AsyncMock(return_value=b"jpeg"), close=AsyncMock()
                )
            ),
        ),
    ):
        task = asyncio.create_task(controller.start())
        try:
            await asyncio.wait_for(entered.wait(), 2)
            assert controller.privacy_ready and not controller.ready
            assert (
                await accessory.async_get_snapshot(
                    {"image-width": 640, "image-height": 360}
                )
                == b"jpeg"
            )
            controller.camera_active = False
            with pytest.raises(RuntimeError, match="stream is disabled"):
                await accessory.start_stream(request, {})
            with pytest.raises(HAPStatusError):
                await accessory.async_get_snapshot(
                    {"image-width": 640, "image-height": 360}
                )
        finally:
            release.set()
            await task
            await controller.close()


async def test_explicit_stream_source_disables_hksv_only(
    hass: HomeAssistant, run_driver, caplog: pytest.LogCaptureFixture
) -> None:
    """Reject an override that cannot share the camera entity's stream."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.demo_camera", "idle")
    source = "rtsp://example.invalid/live"
    accessory = Camera(
        hass,
        run_driver,
        "Camera",
        "camera.demo_camera",
        2,
        {
            CONF_LINKED_MOTION_SENSOR: "binary_sensor.motion",
            "secure_video": True,
            CONF_STREAM_SOURCE: source,
        },
    )
    assert accessory._hksv is None
    assert accessory._management
    with pytest.raises(ValueError, match="Explicit stream_source"):
        await accessory._async_get_hksv_source()
    assert "Secure Video is unavailable with an explicit stream source" in caplog.text


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (b"Connection refused", "connection_refused"),
        (b"Address already in use", "address_or_protocol"),
        (b"Bind failed", "address_or_protocol"),
        (b"Network is unreachable", "address_or_protocol"),
        (b"No route to host", "address_or_protocol"),
        (b"getaddrinfo", "address_or_protocol"),
    ],
)
async def test_live_failure_reports_only_safe_categories(
    hass: HomeAssistant,
    run_driver,
    caplog: pytest.LogCaptureFixture,
    error: bytes,
    expected: str,
) -> None:
    """Retain bounded failure categories without logging URLs or SRTP secrets."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.demo_camera", "idle")
    accessory = Camera(hass, run_driver, "Camera", "camera.demo_camera", 2, {})
    session = {
        "id": "diagnostic",
        "stream_idx": 0,
        FFMPEG_PID: 999999,
        "stream": SimpleNamespace(process=SimpleNamespace(returncode=1)),
    }
    reader = asyncio.StreamReader()
    reader.feed_data(
        b"x" * 4090 + error + b" rtsp://user:secret@host/stream srtp-key-secret"
    )
    reader.feed_eof()
    await accessory._async_log_stderr_stream(reader, session)
    assert session["ffmpeg_diagnostics"] == {expected}
    accessory.sessions["diagnostic"] = session
    with (
        patch(
            "homeassistant.components.homekit.type_cameras.pid_is_alive",
            return_value=False,
        ),
        patch.object(accessory, "set_streaming_available"),
    ):
        assert not await accessory._async_ffmpeg_watch("diagnostic")
    assert expected in caplog.text
    assert "secret" not in caplog.text
    assert "rtsp://" not in caplog.text
    accessory.sessions.clear()


@pytest.mark.parametrize(
    (
        "source_width",
        "source_height",
        "source_profile",
        "source_level",
        "expected_codec",
        "hardware",
    ),
    [
        (1280, 720, 100, 31, "copy", None),
        (2560, 1920, 100, 50, "libx264", None),
        (
            2560,
            1920,
            100,
            50,
            "h264_vaapi",
            HardwareEncoder(
                "h264_vaapi",
                ("-vaapi_device", "/dev/dri/render" + "D128"),
                "format=nv12,hwupload",
                ("-profile:v", "high", "-level:v", "4.0"),
            ),
        ),
    ],
)
async def test_secure_video_live_uses_codec_matching_negotiation(
    hass: HomeAssistant,
    run_driver,
    source_width: int,
    source_height: int,
    source_profile: int,
    source_level: int,
    expected_codec: str,
    hardware: HardwareEncoder | None,
) -> None:
    """Keep compatible video copied and scale incompatible video to the selection."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.demo_camera", "idle")
    accessory = Camera(
        hass, run_driver, "Camera", "camera.demo_camera", 2, {"video_codec": "copy"}
    )
    observed = MediaObservation(
        "h264",
        source_profile,
        source_level,
        source_width,
        source_height,
        None,
        None,
        None,
        None,
        15,
        2,
        15,
        900_000,
        800_000,
        4,
    )
    accessory._hksv = SimpleNamespace(
        privacy_ready=True,
        camera_active=True,
        stream_active=lambda _index: True,
        preserve_source=False,
        observe_live_source=AsyncMock(return_value=observed),
    )
    session = {"id": "live-test", "stream_idx": 0}
    accessory.sessions["live-test"] = session
    selection = {
        "v_profile_id": b"\x02",
        "v_level": b"\x02",
        "width": 1280,
        "height": 720,
        "fps": 15,
        "v_max_bitrate": 1500,
        "a_max_bitrate": 32,
        "address": "127.0.0.1",
        "v_port": 12345,
        "v_srtp_key": "synthetic",
        "v_ssrc": 12345,
    }
    reader = asyncio.StreamReader()
    reader.feed_eof()
    process = SimpleNamespace(
        pid=12345,
        returncode=None,
        stdin=SimpleNamespace(write=MagicMock(), drain=AsyncMock(), close=MagicMock()),
    )

    async def empty_parts():
        await asyncio.Event().wait()
        yield b""

    shared = SimpleNamespace(
        live_parts=empty_parts,
        prepare_live_input=AsyncMock(return_value=0.0),
        close=AsyncMock(),
    )
    ffmpeg_process = SimpleNamespace(
        process=process,
        open=AsyncMock(return_value=True),
        get_reader=AsyncMock(return_value=reader),
    )
    with (
        patch.object(
            accessory, "_async_get_hksv_source", AsyncMock(return_value=shared)
        ),
        patch(
            "homeassistant.components.homekit.type_cameras.HAFFmpeg",
            return_value=ffmpeg_process,
        ),
        patch(
            "homeassistant.components.homekit.type_cameras._HARDWARE_PROBE.select",
            AsyncMock(return_value=hardware),
        ),
        patch.object(accessory, "_async_ffmpeg_watch", AsyncMock(return_value=True)),
    ):
        assert await accessory.start_stream(session, selection)
        accessory._hksv.observe_live_source.assert_awaited_once_with(shared)
        assert session["ffmpeg_shared"] is shared
        output = ffmpeg_process.open.call_args.kwargs["output"]
        assert f"-c:v {expected_codec}" in output
        if expected_codec != "copy":
            assert "scale=1280:720:force_original_aspect_ratio=decrease" in output
            assert "pad=1280:720:(ow-iw)/2:(oh-ih)/2" in output
            if hardware:
                assert "hwupload" in output
                assert (
                    "-vaapi_device"
                    in ffmpeg_process.open.call_args.kwargs["input_source"]
                )
        else:
            assert "scale=" not in output
        accessory._async_stop_ffmpeg_watch("live-test")
        await accessory._release_shared_live(session)
        shared.close.assert_awaited_once()
    accessory.sessions.clear()


async def test_live_permission_rechecked_after_media_observation(
    hass: HomeAssistant, run_driver
) -> None:
    """A HomeKit privacy change during inspection prevents FFmpeg startup."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.demo_camera", "idle")
    accessory = Camera(
        hass, run_driver, "Camera", "camera.demo_camera", 2, {"video_codec": "copy"}
    )
    hksv = SimpleNamespace(
        privacy_ready=True,
        camera_active=True,
        preserve_source=False,
        stream_active=lambda _index: True,
    )

    async def observe(_shared: object) -> None:
        hksv.camera_active = False

    hksv.observe_live_source = observe
    accessory._hksv = hksv
    session = {"id": "privacy-test", "stream_idx": 0}
    selection = {
        "v_profile_id": b"\x02",
        "v_level": b"\x02",
        "width": 1280,
        "height": 720,
        "fps": 15,
        "v_max_bitrate": 1500,
        "a_max_bitrate": 32,
        "address": "127.0.0.1",
        "v_port": 12345,
        "v_srtp_key": "synthetic",
        "v_ssrc": 12345,
    }
    shared = SimpleNamespace(close=AsyncMock())
    with (
        patch.object(
            accessory, "_async_get_hksv_source", AsyncMock(return_value=shared)
        ),
        patch(
            "homeassistant.components.homekit.type_cameras.HAFFmpeg"
        ) as ffmpeg_factory,
    ):
        assert not await accessory.start_stream(session, selection)
        ffmpeg_factory.assert_not_called()
    shared.close.assert_awaited_once()


async def test_shared_live_and_snapshot_privacy(
    hass: HomeAssistant, run_driver
) -> None:
    """Live and snapshots use the shared source and release their own leases."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.test", "idle")
    accessory = Camera(hass, run_driver, "Camera", "camera.test", 2, {})
    accessory._hksv = SimpleNamespace(
        privacy_ready=True,
        camera_active=True,
        stream_active=lambda _index: True,
        preserve_source=False,
        snapshot_allowed=lambda _reason: accessory._hksv.camera_active,
    )
    writer = SimpleNamespace(write=MagicMock(), drain=AsyncMock(), close=MagicMock())
    process = SimpleNamespace(pid=12345, returncode=None, stdin=writer)
    reader = asyncio.StreamReader()
    reader.feed_eof()
    ffmpeg_process = SimpleNamespace(
        process=process,
        open=AsyncMock(return_value=True),
        get_reader=AsyncMock(return_value=reader),
    )
    delivered = asyncio.Event()
    hold = asyncio.Event()

    async def parts():
        yield b"initialization"
        yield b"media"
        delivered.set()
        await hold.wait()

    shared = SimpleNamespace(
        live_parts=parts,
        prepare_live_input=AsyncMock(return_value=0.0),
        image=AsyncMock(return_value=b"jpeg"),
        close=AsyncMock(),
    )
    selection = {
        "v_profile_id": b"\x02",
        "v_level": b"\x02",
        "width": 1280,
        "height": 720,
        "fps": 15,
        "v_max_bitrate": 1500,
        "a_max_bitrate": 32,
        "address": "127.0.0.1",
        "v_port": 12345,
        "v_srtp_key": "synthetic",
        "v_ssrc": 12345,
    }
    session = {"id": "shared", "stream_idx": 0}
    accessory.sessions["shared"] = session
    with (
        patch.object(
            accessory, "_async_get_hksv_source", AsyncMock(return_value=shared)
        ),
        patch(
            "homeassistant.components.homekit.type_cameras.HAFFmpeg",
            return_value=ffmpeg_process,
        ),
        patch.object(accessory, "_async_ffmpeg_watch", AsyncMock(return_value=True)),
    ):
        assert await accessory.start_stream(session, selection)
        await asyncio.wait_for(delivered.wait(), 2)
        assert (
            ffmpeg_process.open.call_args.kwargs["input_source"]
            == "-readrate 1 -i pipe:0"
        )
        assert writer.write.call_args_list == [call(b"initialization"), call(b"media")]
        assert (
            await accessory.async_get_snapshot(
                {"image-width": 640, "image-height": 360}
            )
            == b"jpeg"
        )
        shared.close.assert_awaited_once()
        await accessory._release_shared_live(session)
        assert shared.close.await_count == 2
        accessory._async_stop_ffmpeg_watch("shared")
    accessory.sessions.clear()


async def test_shared_live_privacy_change_releases_reference(
    hass: HomeAssistant, run_driver
) -> None:
    """A privacy change while acquiring the shared stream prevents FFmpeg startup."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.test", "idle")
    accessory = Camera(hass, run_driver, "Camera", "camera.test", 2, {})
    status = SimpleNamespace(
        privacy_ready=True,
        camera_active=True,
        preserve_source=False,
        stream_active=lambda _index: True,
    )
    accessory._hksv = status
    shared = SimpleNamespace(close=AsyncMock())

    async def acquire():
        status.camera_active = False
        return shared

    selection = {
        "v_profile_id": b"\x02",
        "v_level": b"\x02",
        "width": 1280,
        "height": 720,
        "fps": 15,
        "v_max_bitrate": 1500,
        "a_max_bitrate": 32,
        "address": "127.0.0.1",
        "v_port": 12345,
        "v_srtp_key": "synthetic",
        "v_ssrc": 12345,
    }
    with (
        patch.object(accessory, "_async_get_hksv_source", side_effect=acquire),
        patch("homeassistant.components.homekit.type_cameras.HAFFmpeg") as factory,
    ):
        assert not await accessory.start_stream(
            {"id": "privacy", "stream_idx": 0}, selection
        )
        shared.close.assert_awaited_once()
        factory.assert_not_called()


async def test_shared_snapshot_checks_privacy_after_decode(
    hass: HomeAssistant, run_driver
) -> None:
    """Do not return a frame if privacy changes while a keyframe is decoded."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.test", "idle")
    accessory = Camera(hass, run_driver, "Camera", "camera.test", 2, {})
    status = SimpleNamespace(camera_active=True)
    status.snapshot_allowed = lambda _reason: status.camera_active
    accessory._hksv = status

    async def image(_width, _height):
        status.camera_active = False
        return b"frame"

    shared = SimpleNamespace(image=image, close=AsyncMock())
    with (
        patch.object(
            accessory, "_async_get_hksv_source", AsyncMock(return_value=shared)
        ),
        pytest.raises(HAPStatusError),
    ):
        await accessory.async_get_snapshot({"image-width": 640, "image-height": 360})
    shared.close.assert_awaited_once()


async def test_live_backpressure_stops_only_live_pipe(
    hass: HomeAssistant, run_driver
) -> None:
    """A stalled live consumer releases its pipe without closing another lease."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.test", "idle")
    accessory = Camera(hass, run_driver, "Camera", "camera.test", 2, {})
    waiting = asyncio.Event()
    writer = SimpleNamespace(
        write=MagicMock(),
        drain=AsyncMock(side_effect=waiting.wait),
        close=MagicMock(),
    )
    process = SimpleNamespace(stdin=writer)

    async def parts():
        yield b"bounded part"

    shared = SimpleNamespace(live_parts=parts, close=AsyncMock())
    async with asyncio.timeout(7):
        await accessory._feed_shared_live(SimpleNamespace(process=process), shared)
    writer.write.assert_called_once_with(b"bounded part")
    writer.close.assert_called_once()
    shared.close.assert_not_awaited()


async def test_live_stop_closes_pipe_and_waits_for_process(
    hass: HomeAssistant, run_driver
) -> None:
    """A real child reading stdin exits when its shared input lease is released."""
    import sys  # noqa: PLC0415

    from homeassistant.components.homekit.type_cameras import (  # noqa: PLC0415
        FFMPEG_INPUT_TASK,
        FFMPEG_SHARED,
    )

    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.test", "idle")
    accessory = Camera(hass, run_driver, "Camera", "camera.test", 2, {})
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "import sys; sys.stdin.buffer.read()",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    waiting = asyncio.Event()

    async def parts():
        yield b"media"
        await waiting.wait()

    shared = SimpleNamespace(live_parts=parts, close=AsyncMock())
    stream = SimpleNamespace(process=process)
    feeder = asyncio.create_task(accessory._feed_shared_live(stream, shared))
    session = {
        "id": "stopping",
        "stream": stream,
        FFMPEG_INPUT_TASK: feeder,
        FFMPEG_SHARED: shared,
    }
    accessory.sessions["stopping"] = session
    try:
        await asyncio.sleep(0.1)
        async with asyncio.timeout(5):
            await accessory.stop_stream(session)
        assert process.returncode == 0
        shared.close.assert_awaited_once()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        accessory.sessions.clear()


async def test_live_exit_releases_shared_source_and_audio_proxy(
    hass: HomeAssistant, run_driver
) -> None:
    """An unexpectedly exited encoder releases its shared lease and audio proxy."""
    from homeassistant.components.homekit.type_cameras import AUDIO_PROXY, FFMPEG_SHARED  # noqa: PLC0415

    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.test", "idle")
    accessory = Camera(hass, run_driver, "Camera", "camera.test", 2, {})
    shared = SimpleNamespace(close=AsyncMock())
    proxy = SimpleNamespace(async_stop=AsyncMock())
    session = {
        "id": "ended",
        "stream_idx": 0,
        FFMPEG_PID: 12345,
        "stream": SimpleNamespace(process=SimpleNamespace(returncode=1)),
        FFMPEG_SHARED: shared,
        AUDIO_PROXY: proxy,
    }
    accessory.sessions["ended"] = session
    with (
        patch(
            "homeassistant.components.homekit.type_cameras.pid_is_alive",
            return_value=False,
        ),
        patch.object(accessory, "set_streaming_available"),
    ):
        assert not await accessory._async_ffmpeg_watch("ended")
    shared.close.assert_awaited_once()
    proxy.async_stop.assert_awaited_once()
    accessory.sessions.clear()


async def test_snapshot_privacy_change_during_release(
    hass: HomeAssistant, run_driver
) -> None:
    """No frame is returned if privacy is disabled during provider cleanup."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.test", "idle")
    accessory = Camera(hass, run_driver, "Camera", "camera.test", 2, {})
    status = SimpleNamespace(camera_active=True)
    status.snapshot_allowed = lambda _reason: status.camera_active
    accessory._hksv = status

    async def close():
        await asyncio.sleep(0)
        status.camera_active = False

    shared = SimpleNamespace(image=AsyncMock(return_value=b"frame"), close=close)
    with (
        patch.object(
            accessory, "_async_get_hksv_source", AsyncMock(return_value=shared)
        ),
        pytest.raises(HAPStatusError),
    ):
        await accessory.async_get_snapshot({"image-width": 640, "image-height": 360})


async def test_snapshot_without_keyframe_times_out_and_releases_source(
    hass: HomeAssistant, run_driver
) -> None:
    """An unavailable keyframe is bounded and its stream lease is released."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.test", "idle")
    accessory = Camera(hass, run_driver, "Camera", "camera.test", 2, {})
    accessory._hksv = SimpleNamespace(snapshot_allowed=lambda _reason: True)

    async def never(*_args):
        await asyncio.Event().wait()

    shared = SimpleNamespace(image=AsyncMock(side_effect=never), close=AsyncMock())
    with (
        patch("homeassistant.components.homekit.type_cameras.SNAPSHOT_TIMEOUT", 0.01),
        patch.object(
            accessory, "_async_get_hksv_source", AsyncMock(return_value=shared)
        ),
        pytest.raises(TimeoutError),
    ):
        await accessory.async_get_snapshot({"image-width": 640, "image-height": 360})
    shared.close.assert_awaited_once()


async def test_snapshot_source_acquisition_is_bounded(
    hass: HomeAssistant, run_driver
) -> None:
    """A source that never opens cannot hold a snapshot request indefinitely."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.test", "idle")
    accessory = Camera(hass, run_driver, "Camera", "camera.test", 2, {})
    accessory._hksv = SimpleNamespace(snapshot_allowed=lambda _reason: True)

    async def never(*_args):
        await asyncio.Event().wait()

    with (
        patch("homeassistant.components.homekit.type_cameras.SNAPSHOT_TIMEOUT", 0.01),
        patch.object(accessory, "_async_get_hksv_source", AsyncMock(side_effect=never)),
        pytest.raises(TimeoutError),
    ):
        await accessory.async_get_snapshot({"image-width": 640, "image-height": 360})


async def test_default_encoder_outputs_negotiated_size_profile_and_level(
    hass: HomeAssistant, run_driver
) -> None:
    """A real 4 MP input is encoded to HomeKit's negotiated 720p format."""
    from io import BytesIO  # noqa: PLC0415
    import shlex  # noqa: PLC0415

    import av  # noqa: PLC0415

    binary = shutil.which("ffmpeg")
    if not binary:
        pytest.skip("ffmpeg unavailable")
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.test", "idle")
    accessory = Camera(hass, run_driver, "Camera", "camera.test", 2, {})
    selection = {
        "v_profile_id": b"\x02",
        "v_level": b"\x02",
        "width": 1280,
        "height": 720,
        "fps": 15,
    }
    _, codec, options, hardware = await accessory._live_video_parameters(selection)
    assert codec == "libx264"
    assert hardware is None
    process = await asyncio.create_subprocess_exec(
        binary,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=2560x1920:r=15",
        "-frames:v",
        "2",
        "-c:v",
        codec,
        *shlex.split(options),
        "-r",
        "15",
        "-movflags",
        "frag_keyframe+empty_moov",
        "-f",
        "mp4",
        "pipe:1",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    async with asyncio.timeout(15):
        output, stderr = await process.communicate()
    assert process.returncode == 0, stderr.decode(errors="replace")
    with av.open(BytesIO(output), format="mp4") as container:
        video = container.streams.video[0]
        assert (video.width, video.height) == (1280, 720)
        assert video.codec_context.profile == "High"
        assert video.codec_context.extradata[3] == 40
        assert video.average_rate == 15
        assert len(list(container.decode(video=0))) == 2


@pytest.mark.usefixtures("socket_enabled")
@pytest.mark.parametrize(("burst", "min_duration"), [(0, 2.0), (2, 0.8)])
async def test_ffmpeg_paces_shared_input_rtp(burst: int, min_duration: float) -> None:
    """A prebuffered fMP4 input is sent over RTP at media time, not in a burst."""
    ffmpeg_binary = shutil.which("ffmpeg")
    if ffmpeg_binary is None:
        pytest.skip("FFmpeg is not installed")
    producer = await asyncio.create_subprocess_exec(
        ffmpeg_binary,
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=160x120:rate=15",
        "-t",
        "4",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-g",
        "15",
        "-movflags",
        "frag_keyframe+empty_moov+default_base_moof",
        "-f",
        "mp4",
        "pipe:1",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    media, error = await producer.communicate()
    assert producer.returncode == 0, error.decode()
    arrivals: list[float] = []
    loop = asyncio.get_running_loop()

    class Receiver(asyncio.DatagramProtocol):
        def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
            if len(data) >= 12 and data[1] & 0x7F == 96:
                arrivals.append(loop.time())

    transport, _ = await loop.create_datagram_endpoint(
        Receiver, local_addr=("127.0.0.1", 0)
    )
    port = transport.get_extra_info("sockname")[1]
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            ffmpeg_binary,
            "-v",
            "error",
            "-readrate",
            "1",
            "-readrate_initial_burst",
            str(burst),
            "-i",
            "pipe:0",
            "-map",
            "0:v:0",
            "-an",
            "-c:v",
            "copy",
            "-f",
            "rtp",
            f"rtp://127.0.0.1:{port}",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, error = await asyncio.wait_for(process.communicate(media), 12)
        assert process.returncode == 0, error.decode()
        assert len(arrivals) > 10
        assert arrivals[-1] - arrivals[0] >= min_duration
    finally:
        if process is not None and process.returncode is None:
            process.kill()
            await process.wait()
        transport.close()


@pytest.mark.parametrize(("preserve", "expected"), [(True, "copy"), (False, "libx264")])
async def test_live_native_preference(
    hass: HomeAssistant, run_driver, preserve: bool, expected: str
) -> None:
    """Prefer H.264 source video only when explicitly enabled for the camera."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.test", "idle")
    accessory = Camera(
        hass, run_driver, "Camera", "camera.test", 2, {"video_codec": "copy"}
    )
    observed = MediaObservation(
        "h264",
        100,
        50,
        2560,
        1920,
        None,
        None,
        None,
        None,
        10,
        10,
        10,
        3_000_000,
        2_000_000,
        9,
    )
    accessory._hksv = SimpleNamespace(
        preserve_source=preserve, observe_live_source=AsyncMock(return_value=observed)
    )
    selection = {
        "v_profile_id": b"\x02",
        "v_level": b"\x02",
        "width": 1280,
        "height": 720,
        "fps": 15,
        "v_max_bitrate": 1500,
    }
    with patch(
        "homeassistant.components.homekit.type_cameras._HARDWARE_PROBE.select",
        AsyncMock(return_value=None),
    ):
        _, codec, options, _ = await accessory._live_video_parameters(selection)
    assert codec == expected
    if preserve:
        assert "-bsf:v h264_mp4toannexb" in options
        assert "-tune" not in options


async def test_audio_failure_releases_only_audio_lease(
    hass: HomeAssistant, run_driver
) -> None:
    """An unavailable audio child closes its lease without stopping video."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.test", "idle")
    accessory = Camera(hass, run_driver, "Camera", "camera.test", 2, {})
    accessory._hksv = SimpleNamespace(
        privacy_ready=True, camera_active=True, stream_active=lambda _: True
    )
    audio = SimpleNamespace(
        follow_live_start=lambda _: True, live_initial_burst=0.0, close=AsyncMock()
    )
    video = SimpleNamespace(close=AsyncMock())
    child = SimpleNamespace(open=AsyncMock(return_value=False), close=AsyncMock())
    with (
        patch.object(
            accessory, "_async_get_hksv_source", AsyncMock(return_value=audio)
        ),
        patch(
            "homeassistant.components.homekit.type_cameras.HAFFmpeg", return_value=child
        ),
    ):
        await accessory._run_shared_audio({"stream_idx": 0}, video, "audio")
    audio.close.assert_awaited_once()
    child.close.assert_awaited_once()
    video.close.assert_not_awaited()


async def test_blocked_audio_does_not_block_video(
    hass: HomeAssistant, run_driver
) -> None:
    """An audio feeder can block while the video feeder continues independently."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.test", "idle")
    accessory = Camera(hass, run_driver, "Camera", "camera.test", 2, {})
    audio_waiting = asyncio.Event()
    hold = asyncio.Event()
    video_written = asyncio.Event()

    class Writer:
        def __init__(self, audio: bool) -> None:
            self.audio = audio

        def write(self, _data: bytes) -> None:
            if not self.audio:
                video_written.set()

        async def drain(self) -> None:
            if self.audio:
                audio_waiting.set()
                await hold.wait()

        def close(self) -> None:
            pass

    async def parts():
        yield b"part"
        await hold.wait()

    shared = SimpleNamespace(live_parts=parts)
    audio = asyncio.create_task(
        accessory._feed_shared_live(
            SimpleNamespace(process=SimpleNamespace(stdin=Writer(True))), shared
        )
    )
    video = asyncio.create_task(
        accessory._feed_shared_live(
            SimpleNamespace(process=SimpleNamespace(stdin=Writer(False))), shared
        )
    )
    try:
        await asyncio.wait_for(audio_waiting.wait(), 1)
        await asyncio.wait_for(video_written.wait(), 1)
    finally:
        audio.cancel()
        video.cancel()
        await asyncio.gather(audio, video, return_exceptions=True)


async def test_native_live_session_stop_releases_video(
    hass: HomeAssistant, run_driver
) -> None:
    """Stopping a native view cancels its sender and closes its shared lease."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.test", "idle")
    accessory = Camera(hass, run_driver, "Camera", "camera.test", 2, {})
    accessory._hksv = SimpleNamespace(
        privacy_ready=True,
        camera_active=True,
        stream_active=lambda _: True,
        preserve_source=True,
    )
    session = {"id": "native-stop", "stream_idx": 0}
    accessory.sessions[session["id"]] = session
    cancelled = asyncio.Event()

    async def parts():
        yield b"init"

    class Sender:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        async def run(self, _parts: object) -> None:
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    shared = SimpleNamespace(
        prepare_live_input=AsyncMock(return_value=0),
        live_parts=parts,
        close=AsyncMock(),
    )
    selection = {
        "v_srtp_key": "unused",
        "v_ssrc": 1,
        "address": "127.0.0.1",
        "v_port": 1234,
    }
    with (
        patch.object(
            accessory, "_async_get_hksv_source", AsyncMock(return_value=shared)
        ),
        patch(
            "homeassistant.components.homekit.type_cameras.NativeVideoSender", Sender
        ),
    ):
        assert (
            await accessory._start_native_live(session, selection, None, {}, shared)
            is True
        )
        await accessory.stop_stream(session)
    assert cancelled.is_set()
    shared.close.assert_awaited_once()
    accessory.sessions.clear()


async def test_native_live_privacy_change_during_sender_start(
    hass: HomeAssistant, run_driver
) -> None:
    """A privacy change during native startup cancels and releases the sender."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.test", "idle")
    accessory = Camera(hass, run_driver, "Camera", "camera.test", 2, {})
    status = SimpleNamespace(
        privacy_ready=True,
        camera_active=True,
        stream_active=lambda _: True,
        preserve_source=True,
    )
    accessory._hksv = status
    cancelled = asyncio.Event()

    async def parts():
        yield b"init"

    class Sender:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        async def run(self, _parts: object) -> None:
            status.camera_active = False
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    shared = SimpleNamespace(
        prepare_live_input=AsyncMock(return_value=0),
        live_parts=parts,
        close=AsyncMock(),
    )
    selection = {
        "v_srtp_key": "unused",
        "v_ssrc": 1,
        "address": "127.0.0.1",
        "v_port": 1234,
    }
    with (
        patch.object(
            accessory, "_async_get_hksv_source", AsyncMock(return_value=shared)
        ),
        patch(
            "homeassistant.components.homekit.type_cameras.NativeVideoSender", Sender
        ),
    ):
        assert (
            await accessory._start_native_live(
                {"id": "privacy", "stream_idx": 0}, selection, None, {}, shared
            )
            is False
        )
    assert cancelled.is_set()
    shared.close.assert_not_awaited()
    await shared.close()


async def test_live_observation_cancellation_releases_source(
    hass: HomeAssistant, run_driver
) -> None:
    """Cancellation during source inspection releases the live session lease."""
    await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})
    hass.states.async_set("camera.test", "idle")
    accessory = Camera(
        hass, run_driver, "Camera", "camera.test", 2, {"video_codec": "copy"}
    )
    shared = SimpleNamespace(close=AsyncMock())
    accessory._hksv = SimpleNamespace(
        privacy_ready=True,
        camera_active=True,
        stream_active=lambda _: True,
        preserve_source=False,
        observe_live_source=AsyncMock(side_effect=asyncio.CancelledError),
    )
    selection = {
        "v_profile_id": b"\x02",
        "v_level": b"\x02",
        "width": 1280,
        "height": 720,
        "fps": 15,
        "v_max_bitrate": 1500,
    }
    with (
        patch.object(
            accessory, "_async_get_hksv_source", AsyncMock(return_value=shared)
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await accessory.start_stream({"id": "cancel", "stream_idx": 0}, selection)
    shared.close.assert_awaited_once()
