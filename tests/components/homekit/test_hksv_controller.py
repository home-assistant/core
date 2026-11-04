"""Isolated lifecycle checks for the experimental HKSV controller."""

import asyncio
import base64
from collections.abc import AsyncIterator
import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from pyhap import hds, hds_protocol, hds_recording, hds_server, hksv_recording, tlv
from pyhap.loader import Loader
import pytest

from homeassistant.components.homekit import hksv_controller as c
from homeassistant.components.homekit.hksv_config import RecordingConfiguration
from homeassistant.components.homekit.hksv_hardware import HardwareEncoder
from homeassistant.components.homekit.hksv_stream import SharedFragment
from homeassistant.components.stream import Orientation


def _driver() -> SimpleNamespace:
    """Create an official HAP catalog and per-session key store."""
    return SimpleNamespace(loader=Loader(), session_shared_keys={})


class Store:
    """Minimal in-memory state store."""

    def __init__(self) -> None:
        """Initialize state."""
        self.data = {"camera_active": 0, "event_snapshots": 0}

    async def async_load(self):
        """Load state."""
        return self.data

    async def async_save(self, data):
        """Save state."""
        self.data = data

    def async_delay_save(self, callback, delay):
        """Save a snapshot."""
        self.data = callback()


class HDS:
    """Fake transport server."""

    def __init__(self) -> None:
        """Initialize transport state."""
        self.started = False
        self.closed = False
        self.owner_closed = None

    async def start(self) -> None:
        """Start the fake transport."""
        self.started = True

    async def stop(self) -> None:
        """Close the fake transport."""
        self.closed = True

    port = 4321

    def register_transport(self, secret: bytes, salt: bytes) -> bytes:
        """Prepare an authenticated transport."""
        assert self.started and secret == b"x" * 32 and salt == b"y" * 32
        return b"z" * 32


def test_session_and_lifecycle() -> None:
    """Session setup and cleanup preserve state."""

    async def run():
        async def source():
            return None

        store = Store()
        controller = c.HKSVController(_driver(), source, "ffmpeg", store)
        hds = controller.hds = HDS()
        assert controller.active is False
        await controller.start()
        assert hds.started and not controller.camera_active
        assert controller.services.event_snapshots.value == 0
        address = ("127.0.0.1", 1234)
        controller.driver.session_shared_keys[address] = b"x" * 32
        request = tlv.encode(
            b"\x01", b"\0", b"\x02", b"\0", b"\x03", b"y" * 32, to_base64=True
        )
        controller.services.setup.broker = MagicMock()
        response = controller.services.setup.client_update_value(
            request, sender_client_addr=address
        )
        fields = tlv.decode(response, from_base64=True)
        assert fields[b"\x03"] == b"z" * 32
        assert tlv.decode(fields[b"\x02"])[b"\x01"] == (4321).to_bytes(2, "little")
        await controller.close()
        assert hds.closed and store.data["camera_active"] is False

    asyncio.run(run())


def test_encoder_failure_is_bounded_and_unstarted_stream_not_reserved() -> None:
    """Failures retry only within the configured bound."""

    async def run():
        async def source():
            return None

        ctl = c.HKSVController(_driver(), source, "ffmpeg", Store())
        ctl._ready = True
        ctl.active = True
        ctl.configuration = object()

        class Process:
            returncode = 0

            def __init__(self) -> None:
                self._task = asyncio.create_task(asyncio.sleep(0))
                self.stopped = False
                self.running = True

            async def wait(self):
                await self._task

            async def stop(self):
                self.stopped = True

        original_sleep = c.asyncio.sleep

        async def no_delay(_):
            await original_sleep(0)

        c.asyncio.sleep = no_delay
        scheduled = []
        ctl._schedule_reconcile = lambda: scheduled.append(True)
        try:
            for _ in range(4):
                proc = Process()
                ctl._process = proc
                ctl._process_key = ("key", False)
                stream = ctl._open_recording(object(), 1)
                assert not ctl._stream_active
                await stream.aclose()
                await ctl._monitor(proc)
                assert proc.stopped and ctl._process is None
            assert len(scheduled) == 3
            assert ctl._restart_attempts == 3
        finally:
            c.asyncio.sleep = original_sleep

    asyncio.run(run())


def test_snapshot_permissions() -> None:
    """Snapshot requests follow operating permissions."""

    async def source():
        return None

    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    controller._ready = True
    controller._privacy_ready = True
    controller.services.event_snapshots.set_value(0, should_notify=False)
    assert controller.snapshot_allowed(0)
    assert not controller.snapshot_allowed(1)
    assert not controller.snapshot_allowed(None)
    controller.services.event_snapshots.set_value(1, should_notify=False)
    controller.services.periodic_snapshots.set_value(0, should_notify=False)
    assert not controller.snapshot_allowed(0)
    assert controller.snapshot_allowed(1)
    assert not controller.snapshot_allowed(None)
    controller.camera_active = False
    assert not controller.snapshot_allowed(0)
    assert not controller.snapshot_allowed(1)


def test_writes_fail_closed_before_state_load() -> None:
    """Reject writes before restoring privacy state."""

    async def source():
        return None

    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    try:
        controller.services.camera_active.client_update_value(0)
    except RuntimeError:
        pass
    else:
        raise AssertionError("accepted write before state load")
    assert controller.services.camera_active.value == 1
    assert not controller.snapshot_allowed(None)


def test_shared_source_attached_and_detached() -> None:
    """Detach the shared provider during shutdown."""

    async def run():
        class Shared:
            orientation = Orientation.NO_TRANSFORM
            closed = False

            async def fragments(self):
                yield object()

            async def close(self) -> None:
                self.closed = True

        shared = Shared()

        async def source():
            return shared

        class Process:
            running = True
            stopped = False

            def __init__(self, command, seconds, limit) -> None:
                self.command = command
                self.input_data = None

            async def start(self, input_data):
                self.input_data = input_data

            async def wait(self):
                await asyncio.Event().wait()

            async def stop(self):
                self.stopped = True
                assert self.input_data is not None
                await self.input_data.aclose()

        ctl = c.HKSVController(_driver(), source, "ffmpeg", Store())
        ctl.hds = HDS()
        ctl.active = True
        ctl.configuration = SimpleNamespace(
            prebuffer_ms=4000, profile=0, level=2, width=320, height=240, fps=15
        )
        with (
            patch.object(c, "RecordingProcess", Process),
            patch.object(ctl, "_probe_copy", return_value=(False, False)),
            patch.object(
                c._HARDWARE_PROBE, "select", new_callable=AsyncMock, return_value=None
            ),
            patch.object(
                c, "ffmpeg_command", return_value=["ffmpeg", "-i", "pipe:0"]
            ) as command,
        ):
            await ctl._reconcile()
            assert ctl._process is not None
            assert command.call_args.args[1] == ["-i", "pipe:0"]
            proc = ctl._process
            await ctl.close()
            assert proc.stopped and shared.closed

    asyncio.run(run())


async def test_hardware_failure_switches_to_software(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quarantine a failed device and schedule a software restart."""

    async def source():
        return None

    class FailedProcess:
        returncode = 1
        stopped = False

        async def wait(self) -> None:
            return None

        async def stop(self) -> None:
            self.stopped = True

    class Probe:
        failed = None

        def report_failure(self, codec: str) -> None:
            self.failed = codec

    probe = Probe()
    monkeypatch.setattr(c, "_HARDWARE_PROBE", probe)
    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    process = FailedProcess()
    controller._process = process
    controller._active_hardware = HardwareEncoder("h264_vaapi", (), "", ())
    restarts = []
    controller._schedule_reconcile = lambda: restarts.append(True)
    monkeypatch.setattr(c.asyncio, "sleep", AsyncMock())
    await controller._monitor(process)
    assert process.stopped
    assert probe.failed == "h264_vaapi"
    assert controller._force_software
    assert restarts == [True]


async def test_audio_copy_failure_does_not_quarantine_hardware(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retry audio encoding before marking hardware video encoding as failed."""

    async def source() -> None:
        return None

    class FailedProcess:
        returncode = 1

        async def wait(self) -> None:
            return None

        async def stop(self) -> None:
            return None

    probe = SimpleNamespace(report_failure=MagicMock())
    monkeypatch.setattr(c, "_HARDWARE_PROBE", probe)
    monkeypatch.setattr(c.asyncio, "sleep", AsyncMock())
    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    controller._schedule_reconcile = lambda: None
    process = FailedProcess()
    hardware = HardwareEncoder("h264_vaapi", (), "", ())
    controller._process = process
    controller._active_hardware = hardware
    controller._active_copy = (False, True)
    await controller._monitor(process)
    assert controller._audio_copy_disabled
    assert not controller._force_software
    probe.report_failure.assert_not_called()

    controller._process = process
    controller._active_hardware = hardware
    controller._active_copy = (False, False)
    await controller._monitor(process)
    assert controller._force_software
    probe.report_failure.assert_called_once_with("h264_vaapi")


async def test_hardware_runtime_failure_restarts_shared_stream_in_software(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed hardware process restarts recording with software encoding."""
    started_software = asyncio.Event()
    hardware = HardwareEncoder("h264_vaapi", (), "", ())
    reports: list[str] = []
    commands: list[HardwareEncoder | None] = []

    class Probe:
        async def select(self, *_args):
            return hardware

        def report_failure(self, codec: str) -> None:
            reports.append(codec)

    class Shared:
        orientation = Orientation.NO_TRANSFORM

        async def fragments(self):
            yield object()

        async def close(self) -> None:
            return None

    async def source():
        return Shared()

    def command(*_args, hardware=None, **_kwargs):
        commands.append(hardware)
        return [hardware.codec if hardware else "libx264"]

    class Process:
        running = True

        def __init__(self, args, _seconds, _limit) -> None:
            self.is_hardware = args[0] != "libx264"
            self.returncode = 1 if self.is_hardware else None
            self.input_data = None

        async def start(self, input_data) -> None:
            self.input_data = input_data
            if not self.is_hardware:
                started_software.set()

        async def wait(self) -> None:
            if not self.is_hardware:
                await asyncio.Event().wait()

        async def stop(self) -> None:
            assert self.input_data is not None
            await self.input_data.aclose()

    original_sleep = asyncio.sleep

    async def fast_sleep(_delay: float) -> None:
        await original_sleep(0)

    monkeypatch.setattr(c, "_HARDWARE_PROBE", Probe())
    monkeypatch.setattr(c, "RecordingProcess", Process)
    monkeypatch.setattr(c, "ffmpeg_command", command)
    monkeypatch.setattr(c.asyncio, "sleep", fast_sleep)
    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    controller.hds = HDS()
    monkeypatch.setattr(
        controller, "_probe_copy", AsyncMock(return_value=(False, False))
    )
    controller._ready = True
    controller.active = True
    controller.configuration = RecordingConfiguration(
        4000, 1, 4000, 0, 2, 500, 1000, 320, 240, 15, 0, 1, 0, 2, 32
    )
    try:
        await controller._reconcile()
        await asyncio.wait_for(started_software.wait(), 2)
        assert commands == [hardware, None]
        assert reports == ["h264_vaapi"]
        assert controller._process is not None
    finally:
        await controller.close()


@pytest.mark.parametrize(("seconds", "milliseconds"), [(4, 4000), (8, 8000)])
def test_selected_prebuffer_capability(seconds: int, milliseconds: int) -> None:
    """Advertise the selected recording pre-roll without starting a process."""

    async def source():
        return None

    controller = c.HKSVController(
        _driver(), source, "ffmpeg", Store(), prebuffer_seconds=seconds
    )
    assert controller.capabilities.prebuffer_ms == milliseconds
    assert not controller.active
    assert controller._process is None


def test_invalid_prebuffer_rejected() -> None:
    """Unsupported pre-roll values cannot be advertised."""

    async def source():
        return None

    with pytest.raises(ValueError, match="prebuffer"):
        c.HKSVController(_driver(), source, "ffmpeg", Store(), prebuffer_seconds=6)


async def test_recording_request_counts_and_safe_logging(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Count delegated requests and label completion without claiming an ACK."""

    async def source() -> None:
        return None

    class Process:
        running = True

        async def fragments(self) -> AsyncIterator[bytes]:
            yield b"initialization"
            yield b"media"

    controller = c.HKSVController(
        _driver(), source, "ffmpeg", Store(), camera_entity_id="camera.test"
    )
    caplog.set_level(logging.INFO, logger=c.__name__)
    with pytest.raises(ValueError):
        controller._open_recording(object(), 1)
    assert controller._hds_rejected == 1
    assert "category=inactive" in caplog.text
    controller._ready = True
    controller.active = True
    controller.configuration = object()
    controller._process = Process()
    recording = controller._open_recording(object(), 2)
    controller.active = False
    assert [fragment async for fragment in recording] == [
        (b"initialization", False),
        (b"media", True),
    ]
    assert controller._hds_accepted == 1
    assert controller._hds_final_offered == 1
    assert "delivery and acknowledgement not observed by delegate" in caplog.text
    assert "media" not in caplog.text


async def test_restored_recording_waits_for_native_discovery() -> None:
    """The restored recording cannot acquire the provider while probing owns it."""
    discovery_started = asyncio.Event()
    finish_discovery = asyncio.Event()
    acquisitions = []

    async def source():
        raise AssertionError("the stubbed reconciliation must own acquisition")

    store = Store()
    store.data = {"selected": "eA==", "active": 1, "camera_active": 1}
    controller = c.HKSVController(_driver(), source, "ffmpeg", store)
    controller.hds = HDS()

    async def discover():
        acquisitions.append("probe-open")
        discovery_started.set()
        await finish_discovery.wait()
        acquisitions.append("probe-close")

    async def reconcile():
        acquisitions.append("recording-open")

    with (
        patch.object(c, "parse_selected", return_value={}),
        patch.object(RecordingConfiguration, "from_mapping", return_value=object()),
        patch.object(controller, "_discover_native", side_effect=discover),
        patch.object(controller, "_reconcile", side_effect=reconcile),
    ):
        startup = asyncio.create_task(controller.start())
        await discovery_started.wait()
        await asyncio.sleep(0)
        assert acquisitions == ["probe-open"]
        assert controller._reconcile_task is None
        finish_discovery.set()
        await startup
        await controller._reconcile_task
        assert acquisitions == ["probe-open", "probe-close", "recording-open"]
    await controller.close()


async def test_close_during_native_discovery_does_not_start_listener() -> None:
    """Closing while discovery is pending must not reopen the listener."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def source() -> None:
        return None

    async def discover() -> None:
        started.set()
        await release.wait()

    store = Store()
    store.data = {"camera_active": 1}
    controller = c.HKSVController(_driver(), source, "ffmpeg", store)
    hds = controller.hds = HDS()
    with patch.object(controller, "_discover_native", side_effect=discover):
        startup = asyncio.create_task(controller.start())
        await started.wait()
        await controller.close()
        release.set()
        await startup
    assert hds.closed
    assert not hds.started


async def test_final_fragment_is_counted_when_transport_closes_generator(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The official HDS manager closes the producer after its last packet."""

    async def source() -> None:
        return None

    class Process:
        running = True

        async def fragments(self) -> AsyncIterator[bytes]:
            yield b"initialization"
            yield b"media"

    controller = c.HKSVController(
        _driver(), source, "ffmpeg", Store(), camera_entity_id="camera.test"
    )
    controller._ready = True
    controller.active = True
    controller.configuration = object()
    controller._process = Process()
    connection = MagicMock()
    connection.drain = AsyncMock()

    def sent(_protocol: str, _topic: str, message: dict[str, Any]) -> None:
        if message["packets"][0]["metadata"]["dataType"] == "mediaInitialization":
            controller.active = False

    connection.send_event.side_effect = sent
    manager = hds_recording.RecordingStreamManager(
        connection,
        lambda stream_id: controller._recording_packets(connection, stream_id),
    )
    manager._stream_id = 7
    caplog.set_level(logging.INFO, logger=c.__name__)
    await manager._stream()
    assert connection.send_event.call_count == 2
    assert connection.send_event.call_args.args[2]["endOfStream"] is True
    assert controller._hds_final_offered == 1
    assert controller._hds_interrupted == 0
    assert not controller._stream_active
    assert "final fragment offered to transport" in caplog.text
    assert "delivery and acknowledgement not observed by delegate" in caplog.text
    assert "producer interrupted" not in caplog.text


def _selected_profile(profile: int) -> bytes:
    """Build a valid selected configuration with the official codec."""
    return hksv_recording.SelectedRecordingConfiguration(
        recording=hksv_recording.SupportedRecordingConfiguration(
            prebuffer_length_ms=4000,
            event_triggers=1,
            media_containers=[
                hksv_recording.MediaContainerConfiguration(fragment_length_ms=4000)
            ],
        ),
        video=hksv_recording.VideoCodecConfiguration(
            codec_type=hksv_recording.VideoCodecType.H264,
            profile=profile,
            level=2,
            bitrate_kbps=1600,
            iframe_interval_ms=4000,
            attributes=[hksv_recording.VideoAttributes(1280, 720, 15)],
        ),
        audio=hksv_recording.AudioCodecConfiguration(
            codec_type=hksv_recording.AudioCodecType.AAC_LC,
            channels=1,
            bitrate_mode=hksv_recording.BitRateMode(0),
            sample_rate=hksv_recording.AudioSampleRate(2),
            max_audio_bitrate_kbps=24,
        ),
    ).encode()


async def test_quality_renegotiation_and_legacy_state() -> None:
    """Preserve legacy selections; request one refresh for a profile change."""

    async def source():
        return None

    store = Store()
    baseline = base64.b64encode(_selected_profile(0)).decode()
    store.data = {"camera_active": 0, "selected": baseline}
    changed = AsyncMock()
    compatible = c.HKSVController(
        _driver(), source, "ffmpeg", store, on_capabilities_changed=changed
    )
    compatible.hds = HDS()
    await compatible.start()
    assert compatible.configuration.profile == 0
    assert compatible._selected_value == baseline
    changed.assert_not_awaited()
    assert store.data["recording_profiles"] == [0, 1, 2]
    await compatible.close()

    high = c.HKSVController(
        _driver(),
        source,
        "ffmpeg",
        store,
        quality="high",
        on_capabilities_changed=changed,
    )
    high.hds = HDS()
    await high.start()
    assert high.capabilities.profiles == (2,)
    assert high.configuration is None
    assert high._selected_value is None
    assert store.data["selected"] is None
    assert store.data["recording_profiles"] == [2]
    changed.assert_awaited_once()
    with pytest.raises(ValueError):
        high._set_configuration(_selected_profile(0))
    high._set_configuration(_selected_profile(2))
    assert high.configuration.profile == 2
    await high.close()

    restarted = c.HKSVController(
        _driver(),
        source,
        "ffmpeg",
        store,
        quality="high",
        on_capabilities_changed=changed,
    )
    restarted.hds = HDS()
    await restarted.start()
    assert restarted.configuration.profile == 2
    changed.assert_awaited_once()
    await restarted.close()


async def test_failed_capability_notification_does_not_block_recording() -> None:
    """Keep the recording lifecycle alive and retry advertisement next startup."""

    async def source():
        return None

    store = Store()
    store.data = {"camera_active": 0, "recording_profiles": [0, 1, 2]}
    failed = AsyncMock(side_effect=RuntimeError("notification failed"))
    controller = c.HKSVController(
        _driver(),
        source,
        "ffmpeg",
        store,
        quality="high",
        on_capabilities_changed=failed,
    )
    controller.hds = HDS()
    await controller.start()
    assert controller._ready
    assert store.data["recording_profiles"] == [0, 1, 2]
    await controller.close()
    changed = AsyncMock()
    restarted = c.HKSVController(
        _driver(),
        source,
        "ffmpeg",
        store,
        quality="high",
        on_capabilities_changed=changed,
    )
    restarted.hds = HDS()
    await restarted.start()
    changed.assert_awaited_once()
    assert store.data["recording_profiles"] == [2]
    await restarted.close()


@pytest.mark.parametrize(
    ("copied", "expected"),
    [
        ((True, False), (True, False)),
        ((False, True), (False, True)),
        ((True, True), (False, True)),
    ],
)
async def test_failed_copied_tracks_fall_back(
    monkeypatch: pytest.MonkeyPatch,
    copied: tuple[bool, bool],
    expected: tuple[bool, bool],
) -> None:
    """Try encoding audio first when the failing track is unknown."""

    async def source():
        return None

    class FailedProcess:
        returncode = 1

        async def wait(self) -> None:
            return None

        async def stop(self) -> None:
            return None

    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    process = FailedProcess()
    controller._process = process
    controller._active_copy = copied
    monkeypatch.setattr(c.asyncio, "sleep", AsyncMock())
    controller._schedule_reconcile = lambda: None
    await controller._monitor(process)
    assert (
        controller._video_copy_disabled,
        controller._audio_copy_disabled,
    ) == expected


async def test_repeated_remux_failure_falls_back_in_stages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A persistent failure falls back to video encoding after audio encoding."""

    async def source() -> None:
        return None

    class FailedProcess:
        returncode = 1

        async def wait(self) -> None:
            return None

        async def stop(self) -> None:
            return None

    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    process = FailedProcess()
    controller._process = process
    controller._active_copy = (True, True)
    monkeypatch.setattr(c.asyncio, "sleep", AsyncMock())
    controller._schedule_reconcile = lambda: None
    await controller._monitor(process)
    assert not controller._video_copy_disabled
    assert controller._audio_copy_disabled
    controller._process = process
    controller._active_copy = (True, False)
    await controller._monitor(process)
    assert controller._video_copy_disabled
    assert controller._audio_copy_disabled


async def test_known_video_copy_failure_keeps_audio_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A detected video failure must not disable otherwise valid audio copy."""

    async def source() -> None:
        return None

    class FailedProcess:
        returncode = 1

        async def wait(self) -> None:
            return None

        async def stop(self) -> None:
            return None

    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    process = FailedProcess()
    controller._process = process
    controller._active_copy = (True, True)
    controller._video_copy_disabled = True
    monkeypatch.setattr(c.asyncio, "sleep", AsyncMock())
    controller._schedule_reconcile = lambda: None
    await controller._monitor(process)
    assert controller._video_copy_disabled
    assert not controller._audio_copy_disabled


async def test_close_joins_cancelled_monitor_cleanup() -> None:
    """Cancellation cannot orphan either part of a recording lease."""
    gate = asyncio.Event()
    stopping = asyncio.Event()
    closing = asyncio.Event()

    class Process:
        returncode = 0

        async def wait(self) -> None:
            return

        async def stop(self) -> None:
            stopping.set()
            await gate.wait()

    class Shared:
        orientation = Orientation.NO_TRANSFORM
        closed = False

        async def close(self) -> None:
            closing.set()
            await gate.wait()
            self.closed = True

    async def source() -> None:
        return None

    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    controller.hds = HDS()
    process = Process()
    shared = Shared()
    controller._process = process
    controller._shared = shared
    controller._monitor_task = asyncio.create_task(controller._monitor(process))
    await stopping.wait()
    controller._monitor_task.cancel()
    first = asyncio.create_task(controller.close())
    await asyncio.sleep(0)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    second = asyncio.create_task(controller.close())
    await asyncio.sleep(0)
    assert not second.done()
    gate.set()
    await second
    assert closing.is_set()
    assert shared.closed


async def test_start_failure_retries_and_recovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transient acquisition failure restarts without another setting write."""
    shared = MagicMock()
    shared.orientation = Orientation.NO_TRANSFORM
    shared.close = AsyncMock()
    source = AsyncMock(side_effect=[RuntimeError("transient"), shared])
    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    controller.active = True
    controller._ready = True
    controller.configuration = RecordingConfiguration(
        4000, 1, 4000, 0, 2, 500, 1000, 320, 240, 15, 0, 1, 0, 2, 32
    )
    process = MagicMock()
    process.start = AsyncMock()
    process.wait = AsyncMock(side_effect=asyncio.CancelledError)
    monkeypatch.setattr(c, "RecordingProcess", lambda *_: process)
    monkeypatch.setattr(
        controller, "_probe_copy", AsyncMock(return_value=(False, False))
    )
    monkeypatch.setattr(c._HARDWARE_PROBE, "select", AsyncMock(return_value=None))
    monkeypatch.setattr(c.asyncio, "sleep", AsyncMock())
    await controller._reconcile()
    assert source.await_count == 2
    assert controller._process is process
    controller._monitor_task.cancel()
    await asyncio.gather(controller._monitor_task, return_exceptions=True)


async def test_start_failure_stops_at_retry_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated acquisition failures cannot spin indefinitely."""
    source = AsyncMock(side_effect=RuntimeError("unavailable"))
    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    controller.active = True
    controller._ready = True
    controller.configuration = RecordingConfiguration(
        4000, 1, 4000, 0, 2, 500, 1000, 320, 240, 15, 0, 1, 0, 2, 32
    )
    monkeypatch.setattr(c.asyncio, "sleep", AsyncMock())
    await controller._reconcile()
    assert source.await_count == 4
    assert controller._restart_attempts == 3


async def test_start_failure_retry_respects_privacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disabling the camera during retry prevents another acquisition."""
    source = AsyncMock(side_effect=RuntimeError("unavailable"))
    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    controller.active = True
    controller._ready = True
    controller.configuration = RecordingConfiguration(
        4000, 1, 4000, 0, 2, 500, 1000, 320, 240, 15, 0, 1, 0, 2, 32
    )

    async def disable(_delay: float) -> None:
        controller.camera_active = False

    monkeypatch.setattr(c.asyncio, "sleep", disable)
    await controller._reconcile()
    assert source.await_count == 1


async def test_close_joins_cancelled_lease_close() -> None:
    """A lease remains owned when shutdown cancels its original waiter."""
    gate = asyncio.Event()
    entered = asyncio.Event()

    class Process:
        returncode = 0

        async def wait(self) -> None:
            return

        async def stop(self) -> None:
            return

    class Shared:
        orientation = Orientation.NO_TRANSFORM
        closed = False

        async def close(self) -> None:
            entered.set()
            await gate.wait()
            self.closed = True

    async def source() -> None:
        return None

    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    controller.hds = HDS()
    controller._process = process = Process()
    controller._shared = shared = Shared()
    controller._monitor_task = asyncio.create_task(controller._monitor(process))
    await entered.wait()
    controller._monitor_task.cancel()
    closing = asyncio.create_task(controller.close())
    await asyncio.sleep(0)
    assert not closing.done()
    gate.set()
    await closing
    assert shared.closed


async def test_observe_live_source_uses_supplied_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Observe the live lease independently and reject a detached lease."""

    class Lease:
        orientation = Orientation.NO_TRANSFORM
        _closed = False
        attached = True

        def snapshot(
            self, *, include_partial: bool = False
        ) -> tuple[SharedFragment, ...]:
            return (SharedFragment(1, 1, b"init", b"data", 4),)

        def _check_attached(self) -> None:
            if not self.attached:
                raise ValueError("detached")

    async def source() -> None:
        return None

    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    lease = Lease()
    observation = SimpleNamespace(observation_seconds=3)
    monkeypatch.setattr(c, "inspect_recording", lambda *_: observation)
    assert await controller.observe_live_source(lease) is observation
    lease.attached = False
    assert await controller.observe_live_source(lease) is None
    lease.attached = True
    lease._closed = True
    assert await controller.observe_live_source(lease) is None


@pytest.mark.parametrize("closed", [False, True])
@pytest.mark.parametrize("delivered", [0, 1, 2])
async def test_recording_privacy_revocation_before_next_yield(
    delivered: int, closed: bool
) -> None:
    """Camera privacy stops output before the next init or media fragment."""

    class Process:
        running = True

        async def fragments(self) -> AsyncIterator[bytes]:
            yield b"init"
            yield b"one"
            yield b"two"

    async def source() -> None:
        return None

    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    controller._ready = True
    controller.active = True
    controller.configuration = object()
    controller._process = Process()
    recording = controller._open_recording(object(), 1)
    for _ in range(delivered):
        await anext(recording)
    controller.camera_active = closed
    controller._closed = closed
    with pytest.raises(StopAsyncIteration):
        await anext(recording)
    assert not controller._stream_active
    controller.camera_active = True
    controller._closed = False
    next_recording = controller._open_recording(object(), 2)
    assert await anext(next_recording) == (b"init", False)
    await next_recording.aclose()
    assert not controller._stream_active


@pytest.mark.parametrize("closed", [False, True])
async def test_recording_privacy_revocation_during_fragment_wait(closed: bool) -> None:
    """A fragment arriving after privacy changes is never sent."""
    waiting = asyncio.Event()
    release = asyncio.Event()

    class Process:
        running = True

        async def fragments(self) -> AsyncIterator[bytes]:
            yield b"init"
            waiting.set()
            await release.wait()
            yield b"private"

    async def source() -> None:
        return None

    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    controller._ready = True
    controller.active = True
    controller.configuration = object()
    controller._process = Process()
    recording = controller._open_recording(object(), 1)
    assert await anext(recording) == (b"init", False)
    next_fragment = asyncio.create_task(anext(recording))
    await waiting.wait()
    controller.camera_active = closed
    controller._closed = closed
    release.set()
    with pytest.raises(StopAsyncIteration):
        await next_fragment
    assert not controller._stream_active
    controller.camera_active = True
    controller._closed = False
    next_recording = controller._open_recording(object(), 2)
    assert await anext(next_recording) == (b"init", False)
    await next_recording.aclose()


async def test_privacy_revocation_closes_fragment_subscription() -> None:
    """Release the media subscription before another recording is accepted."""
    subscriptions = 0

    class Process:
        running = True

        async def fragments(self) -> AsyncIterator[bytes]:
            nonlocal subscriptions
            subscriptions += 1
            try:
                yield b"init"
                yield b"private"
            finally:
                subscriptions -= 1

    async def source() -> None:
        return None

    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    controller._ready = True
    controller.active = True
    controller.configuration = object()
    controller._process = Process()
    recording = controller._open_recording(object(), 1)
    assert await anext(recording) == (b"init", False)
    assert subscriptions == 1
    controller.camera_active = False
    with pytest.raises(StopAsyncIteration):
        await anext(recording)
    assert subscriptions == 0
    controller.camera_active = True
    next_recording = controller._open_recording(object(), 2)
    assert await anext(next_recording) == (b"init", False)
    await next_recording.aclose()
    assert subscriptions == 0


async def test_camera_privacy_cancels_hds_multichunk_transfer() -> None:
    """Revocation stops the SDK manager before the second media chunk."""
    blocked = asyncio.Event()
    chunks: list[bytes] = []
    callbacks = []
    calls = 0

    async def source() -> None:
        return None

    class Process:
        running = True

        async def fragments(self) -> AsyncIterator[bytes]:
            yield b"init"
            yield b"x" * (0x40000 * 3)

    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    controller._ready = True
    controller.active = True
    controller.configuration = object()
    controller._process = Process()
    controller._schedule_reconcile = lambda: None
    connection = MagicMock()
    connection.add_close_callback.side_effect = callbacks.append

    async def drain() -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            blocked.set()
            await asyncio.Event().wait()

    def send_event(_protocol: str, _topic: str, message: dict[str, Any]) -> None:
        packet = message["packets"][0]
        if packet["metadata"]["dataType"] == "mediaFragment":
            chunks.append(packet["data"])

    connection.drain = drain
    connection.send_event.side_effect = send_event
    connection.close.side_effect = lambda: [
        callback(connection) for callback in callbacks
    ]
    controller._connections.add(connection)
    manager = hds_recording.RecordingStreamManager(
        connection,
        lambda stream_id: controller._recording_packets(connection, stream_id),
    )
    manager._stream_id = 1
    manager._task = asyncio.create_task(manager._stream())
    await asyncio.wait_for(blocked.wait(), 2)
    assert controller._recording_owner is connection
    controller._change_camera_active(0)
    with pytest.raises(asyncio.CancelledError):
        await manager._task
    connection.close.assert_called_once_with()
    assert len(chunks) == 1 and len(chunks[0]) == 0x40000
    assert controller._recording_owner is None
    assert not controller._stream_active
    controller._connections.discard(connection)
    controller._change_camera_active(1)
    another = controller._open_recording(object(), 2)
    assert await anext(another) == (b"init", False)
    await another.aclose()
    assert controller._recording_owner is None


@pytest.mark.usefixtures("socket_enabled")
async def test_camera_privacy_closes_authenticated_hds_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Close a real authenticated SDK HDS connection between media chunks."""
    blocked, cancelled, fragment_closed = (
        asyncio.Event(),
        asyncio.Event(),
        asyncio.Event(),
    )
    drain_calls = 0
    original_drain = hds_server.HDSConnection.drain

    async def paused_drain(connection: hds_server.HDSConnection) -> None:
        nonlocal drain_calls
        await original_drain(connection)
        drain_calls += 1
        if drain_calls == 3:
            blocked.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

    monkeypatch.setattr(hds_server.HDSConnection, "drain", paused_drain)

    async def source() -> None:
        return None

    class Process:
        running = True

        async def fragments(self) -> AsyncIterator[bytes]:
            try:
                yield b"init"
                yield b"x" * (0x40000 + 1)
            finally:
                fragment_closed.set()

    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    controller._ready = True
    controller.active = True
    controller.configuration = object()
    controller._process = Process()
    controller._schedule_reconcile = lambda: None
    server = controller.hds
    port = await server.start("127.0.0.1")
    writer = None
    try:
        secret, salt = b"x" * 32, b"y" * 32
        address = ("127.0.0.1", 1234)
        controller.driver.session_shared_keys[address] = secret
        setup = tlv.encode(
            b"\x01", b"\0", b"\x02", b"\0", b"\x03", salt, to_base64=True
        )
        controller.services.setup.broker = MagicMock()
        response = controller.services.setup.client_update_value(
            setup, sender_client_addr=address
        )
        fields = tlv.decode(response, from_base64=True)
        assert fields[b"\x01"] == hds.SETUP_STATUS_SUCCESS
        accessory_salt = fields[b"\x03"]
        outgoing, incoming = hds.derive_keys(secret, salt, accessory_salt)
        crypto = hds.HDSCrypto(incoming, outgoing)
        reader, writer = await asyncio.open_connection("127.0.0.1", port)

        async def send(message: hds_protocol.Message) -> None:
            writer.write(crypto.encrypt_frame(message.encode()))
            await writer.drain()

        async def read() -> hds_protocol.Message:
            header = await asyncio.wait_for(reader.readexactly(4), 2)
            length = int.from_bytes(header[1:], "big")
            frame = bytearray(
                header + await asyncio.wait_for(reader.readexactly(length + 16), 2)
            )
            payload = crypto.decrypt_frame(frame)
            assert payload is not None
            return hds_protocol.Message.decode(payload)

        await send(hds_protocol.request("control", "hello", {}, 1))
        assert (await read()).status == hds_protocol.HDSStatus.SUCCESS
        await send(
            hds_protocol.request(
                "dataSend",
                "open",
                {"streamId": 42, "type": "ipcamera.recording", "target": "controller"},
                2,
            )
        )
        opened = await read()
        assert opened.status == hds_protocol.HDSStatus.SUCCESS
        initialization = await read()
        assert (
            initialization.message["packets"][0]["metadata"]["dataType"]
            == "mediaInitialization"
        )
        first = await read()
        assert first.message["packets"][0]["metadata"]["dataType"] == "mediaFragment"
        assert len(first.message["packets"][0]["data"]) == 0x40000
        await asyncio.wait_for(blocked.wait(), 2)
        assert controller._recording_owner in controller._connections
        controller._change_camera_active(0)
        assert await asyncio.wait_for(reader.read(), 2) == b""
        await asyncio.wait_for(cancelled.wait(), 2)
        await asyncio.wait_for(fragment_closed.wait(), 2)
        assert controller._recording_owner is None
        assert not controller._stream_active
        controller._change_camera_active(1)
        second = controller._open_recording(object(), 43)
        assert await anext(second) == (b"init", False)
        await second.aclose()
    finally:
        if writer is not None:
            writer.close()
            await writer.wait_closed()
        await server.stop()


async def test_reconcile_reenabled_during_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changes during cleanup are reconciled without another settings write."""
    entered, release = asyncio.Event(), asyncio.Event()

    class Previous:
        async def stop(self) -> None:
            entered.set()
            await release.wait()

    lease = MagicMock()
    lease.orientation = Orientation.NO_TRANSFORM
    lease.close = AsyncMock()
    source = AsyncMock(return_value=lease)
    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    controller._ready = True
    controller.active = False
    controller.configuration = RecordingConfiguration(
        4000, 1, 4000, 0, 2, 500, 1000, 320, 240, 15, 0, 1, 0, 2, 32
    )
    controller._process = Previous()
    controller._process_key = (controller.configuration, False)
    process = MagicMock()
    process.start = AsyncMock()
    process.wait = AsyncMock(side_effect=asyncio.CancelledError)
    monkeypatch.setattr(c, "RecordingProcess", lambda *_: process)
    monkeypatch.setattr(
        controller, "_probe_copy", AsyncMock(return_value=(False, False))
    )
    monkeypatch.setattr(c._HARDWARE_PROBE, "select", AsyncMock(return_value=None))
    controller._schedule_reconcile()
    await entered.wait()
    controller.active = True
    controller._schedule_reconcile()
    release.set()
    await controller._reconcile_task
    assert source.await_count == 1
    assert controller._process is process
    controller._monitor_task.cancel()
    await asyncio.gather(controller._monitor_task, return_exceptions=True)


@pytest.mark.parametrize("mode", ["live", "recording"])
async def test_native_probe_uses_previous_contiguous_media(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """A short partial segment can be measured together with the previous segment."""
    fragments = (
        SharedFragment(1, 1, b"init", b"previous", 2),
        SharedFragment(1, 2, b"init", b"partial", 0.5),
    )
    short = SimpleNamespace(observation_seconds=0.5)
    enough = SimpleNamespace(observation_seconds=2.4)
    windows: list[tuple[bytes, ...]] = []

    def inspect(_init: bytes, data: tuple[bytes, ...], _strict: bool) -> object:
        windows.append(data)
        return short if len(data) == 1 else enough

    class Lease:
        orientation = Orientation.NO_TRANSFORM
        _closed = False

        def _check_attached(self) -> None:
            pass

        def snapshot(
            self, *, include_partial: bool = False
        ) -> tuple[SharedFragment, ...]:
            return fragments

    async def source() -> None:
        return None

    monkeypatch.setattr(c, "inspect_recording", inspect)
    monkeypatch.setattr(c, "can_copy_video", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        c.asyncio, "sleep", AsyncMock(side_effect=AssertionError("probe waited"))
    )
    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    config = RecordingConfiguration(
        4000, 1, 4000, 0, 2, 500, 1000, 320, 240, 15, 0, 1, 0, 2, 32
    )
    if mode == "live":
        assert await controller.observe_live_source(Lease()) is enough
    else:
        assert await controller._probe_copy(Lease(), config, False) == (True, False)
    assert windows == [(b"partial",), (b"previous", b"partial")]


@pytest.mark.parametrize(
    "previous",
    [
        SharedFragment(1, 1, b"init", b"previous", 2),
        SharedFragment(2, 2, b"init", b"previous", 2),
        SharedFragment(1, 2, b"old init", b"previous", 2),
    ],
)
async def test_native_probe_does_not_combine_discontinuous_media(
    monkeypatch: pytest.MonkeyPatch, previous: SharedFragment
) -> None:
    """Never combine media separated by a gap, generation, or initialization."""
    short = SimpleNamespace(observation_seconds=0.5)
    windows: list[tuple[bytes, ...]] = []

    def inspect(_init: bytes, data: tuple[bytes, ...], _strict: bool) -> object:
        windows.append(data)
        return short

    class Lease:
        orientation = Orientation.NO_TRANSFORM
        _closed = False

        def _check_attached(self) -> None:
            pass

        def snapshot(
            self, *, include_partial: bool = False
        ) -> tuple[SharedFragment, ...]:
            return previous, SharedFragment(1, 3, b"init", b"partial", 0.5)

    async def source() -> None:
        return None

    monkeypatch.setattr(c, "inspect_recording", inspect)
    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    assert await controller.observe_live_source(Lease()) is short
    assert windows == [(b"partial",)]


async def test_recording_respects_shared_source_orientation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Transform video while preserving independently eligible audio copy."""
    lease = MagicMock()
    lease.orientation = Orientation.ROTATE_RIGHT
    lease.close = AsyncMock()
    source = AsyncMock(return_value=lease)
    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    controller._ready = True
    controller.active = True
    controller.audio_active = True
    controller.configuration = RecordingConfiguration(
        4000, 1, 4000, 0, 2, 500, 1000, 320, 240, 15, 0, 1, 0, 2, 32
    )
    process = MagicMock()
    process.start = AsyncMock()
    process.wait = AsyncMock(side_effect=asyncio.CancelledError)
    command = MagicMock(return_value=["ffmpeg"])
    monkeypatch.setattr(c, "RecordingProcess", lambda *_: process)
    monkeypatch.setattr(c, "ffmpeg_command", command)
    monkeypatch.setattr(controller, "_probe_copy", AsyncMock(return_value=(True, True)))
    monkeypatch.setattr(c._HARDWARE_PROBE, "select", AsyncMock(return_value=None))
    assert await controller.observe_live_source(lease) is None
    await controller._reconcile()
    assert command.call_args.kwargs["copy_video"] is False
    assert command.call_args.kwargs["copy_audio"] is True
    assert command.call_args.kwargs["orientation"] == Orientation.ROTATE_RIGHT
    controller._monitor_task.cancel()
    await asyncio.gather(controller._monitor_task, return_exceptions=True)


async def test_recording_reconciles_changed_source_orientation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A changed orientation restarts recording despite an unchanged source URL."""
    lease = MagicMock()
    lease.orientation = Orientation.MIRROR
    lease.close = AsyncMock()
    source = AsyncMock(return_value=lease)
    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    controller._ready = True
    controller.active = True
    controller.audio_active = True
    controller.configuration = RecordingConfiguration(
        4000, 1, 4000, 0, 2, 500, 1000, 320, 240, 15, 0, 1, 0, 2, 32
    )
    processes = [MagicMock(), MagicMock()]
    for process in processes:
        process.start = AsyncMock()
        process.stop = AsyncMock()
        process.wait = AsyncMock(side_effect=asyncio.Event().wait)
    command = MagicMock(return_value=["ffmpeg"])
    monkeypatch.setattr(c, "RecordingProcess", MagicMock(side_effect=processes))
    monkeypatch.setattr(c, "ffmpeg_command", command)
    monkeypatch.setattr(controller, "_probe_copy", AsyncMock(return_value=(True, True)))
    monkeypatch.setattr(c._HARDWARE_PROBE, "select", AsyncMock(return_value=None))
    await controller._reconcile()
    first_monitor = controller._monitor_task
    try:
        lease.orientation = Orientation.FLIP
        controller._schedule_reconcile()
        await controller._reconcile_task
        assert source.await_count == 2
        processes[0].stop.assert_awaited_once()
        assert controller._process is processes[1]
        assert [call.kwargs["orientation"] for call in command.call_args_list] == [
            Orientation.MIRROR,
            Orientation.FLIP,
        ]
        assert all(call.kwargs["copy_audio"] for call in command.call_args_list)
        assert not any(call.kwargs["copy_video"] for call in command.call_args_list)
    finally:
        tasks = {
            task
            for task in (first_monitor, controller._monitor_task)
            if task is not None
        }
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_orientation_change_during_recording_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A change during process startup is retried with the latest orientation."""
    started, release = asyncio.Event(), asyncio.Event()
    lease = MagicMock()
    lease.orientation = Orientation.MIRROR
    lease.close = AsyncMock()
    source = AsyncMock(return_value=lease)
    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    controller._ready = True
    controller.active = True
    controller.configuration = RecordingConfiguration(
        4000, 1, 4000, 0, 2, 500, 1000, 320, 240, 15, 0, 1, 0, 2, 32
    )
    first, second = MagicMock(), MagicMock()

    async def first_start(_data: object) -> None:
        started.set()
        await release.wait()

    first.start = AsyncMock(side_effect=first_start)
    first.stop = AsyncMock()
    second.start = AsyncMock()
    second.wait = AsyncMock(side_effect=asyncio.Event().wait)
    command = MagicMock(return_value=["ffmpeg"])
    monkeypatch.setattr(c, "RecordingProcess", MagicMock(side_effect=[first, second]))
    monkeypatch.setattr(c, "ffmpeg_command", command)
    monkeypatch.setattr(
        controller, "_probe_copy", AsyncMock(return_value=(False, False))
    )
    monkeypatch.setattr(c._HARDWARE_PROBE, "select", AsyncMock(return_value=None))
    controller._schedule_reconcile()
    try:
        await started.wait()
        lease.orientation = Orientation.FLIP
        controller.source_orientation_changed()
        release.set()
        await controller._reconcile_task
        first.stop.assert_awaited_once()
        assert controller._process is second
        assert [call.kwargs["orientation"] for call in command.call_args_list] == [
            Orientation.MIRROR,
            Orientation.FLIP,
        ]
    finally:
        release.set()
        tasks = {
            task
            for task in (controller._reconcile_task, controller._monitor_task)
            if task is not None
        }
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.parametrize(
    ("ready", "active", "camera_active", "closed"),
    [
        (False, True, True, False),
        (True, False, True, False),
        (True, True, False, False),
        (True, True, True, True),
    ],
)
async def test_orientation_change_does_not_open_inactive_camera(
    ready: bool, active: bool, camera_active: bool, closed: bool
) -> None:
    """Orientation notifications do not bypass loading, shutdown or privacy."""
    source = AsyncMock()
    controller = c.HKSVController(_driver(), source, "ffmpeg", Store())
    controller._ready = ready
    controller.active = active
    controller.camera_active = camera_active
    controller._closed = closed
    controller.configuration = RecordingConfiguration(
        4000, 1, 4000, 0, 2, 500, 1000, 320, 240, 15, 0, 1, 0, 2, 32
    )
    controller.source_orientation_changed()
    if controller._reconcile_task is not None:
        await controller._reconcile_task
    source.assert_not_awaited()
