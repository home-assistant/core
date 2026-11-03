"""Isolated lifecycle checks for the experimental HKSV controller."""

import asyncio
from collections.abc import AsyncIterator
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from pyhap.hap_session import HAPSession
import pyhap.secure_video as s
import pytest

from homeassistant.components.homekit import hksv_controller as c
from homeassistant.components.homekit.hksv_config import RecordingConfiguration
from homeassistant.components.homekit.hksv_hardware import HardwareEncoder


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

    async def close(self) -> None:
        """Close the fake transport."""
        self.closed = True

    def prepare_session(self, secret, salt, owner):
        """Prepare an authenticated session."""
        assert self.started and secret == b"x" * 32 and salt == b"y" * 32
        return 4321, b"z" * 32

    def close_owner(self, owner: object) -> None:
        """Record the closed owner."""
        self.owner_closed = owner


def test_session_and_lifecycle() -> None:
    """Session setup and cleanup preserve state."""

    async def run():
        async def source():
            return None

        store = Store()
        controller = c.HKSVController(source, "ffmpeg", store)
        hds = controller.hds = HDS()
        controller.services.hds = hds
        assert controller.active is False
        await controller.start()
        assert hds.started and not controller.camera_active
        assert controller.services.event_snapshots.value == 0
        session = HAPSession(uuid4(), b"x" * 32)
        request = s.b64(s.tlv((1, b"\0"), (2, b"\0"), (3, b"y" * 32)))
        response = controller.services.setup.client_update_value(
            request, session=session
        )
        assert s.parse_tlv(s.unb64(response))[3] == b"z" * 32
        session.close()
        assert hds.owner_closed is session
        await controller.close()
        assert hds.closed and store.data["camera_active"] is False

    asyncio.run(run())


def test_encoder_failure_is_bounded_and_unstarted_stream_not_reserved() -> None:
    """Failures retry only within the configured bound."""

    async def run():
        async def source():
            return None

        ctl = c.HKSVController(source, "ffmpeg", Store())
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

    controller = c.HKSVController(source, "ffmpeg", Store())
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

    controller = c.HKSVController(source, "ffmpeg", Store())
    session = HAPSession(uuid4(), b"x" * 32)
    try:
        controller.services.camera_active.client_update_value(0, session=session)
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

        ctl = c.HKSVController(source, "ffmpeg", Store())
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
    controller = c.HKSVController(source, "ffmpeg", Store())
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
    controller = c.HKSVController(source, "ffmpeg", Store())
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
    controller = c.HKSVController(source, "ffmpeg", Store())
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

    controller = c.HKSVController(source, "ffmpeg", Store(), prebuffer_seconds=seconds)
    assert controller.capabilities.prebuffer_ms == milliseconds
    assert not controller.active
    assert controller._process is None


def test_invalid_prebuffer_rejected() -> None:
    """Unsupported pre-roll values cannot be advertised."""

    async def source():
        return None

    with pytest.raises(ValueError, match="prebuffer"):
        c.HKSVController(source, "ffmpeg", Store(), prebuffer_seconds=6)


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
        source, "ffmpeg", Store(), camera_entity_id="camera.test"
    )
    caplog.set_level(logging.INFO, logger=c.__name__)
    with pytest.raises(c.HDSReject):
        controller._open_recording(object(), 1)
    assert controller._hds_rejected == 1
    assert "category=inactive" in caplog.text
    controller._ready = True
    controller.active = True
    controller.configuration = object()
    controller._process = Process()
    recording = controller._open_recording(object(), 2)
    controller._closed = True
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
    controller = c.HKSVController(source, "ffmpeg", store)
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


async def test_final_fragment_is_counted_when_transport_closes_generator(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The HDS consumer closes after the last yield without resuming producer."""
    from pyhap.datastream import HDSServer  # noqa: PLC0415

    async def source() -> None:
        return None

    class Process:
        async def fragments(self) -> AsyncIterator[bytes]:
            yield b"initialization"
            yield b"media"

    controller = c.HKSVController(
        source, "ffmpeg", Store(), camera_entity_id="camera.test"
    )
    controller.active = False
    caplog.set_level(logging.INFO, logger=c.__name__)
    send = AsyncMock()
    assert await HDSServer._send_fragments(send, 7, controller._recording(Process()))
    assert controller._hds_final_offered == 1
    assert controller._hds_interrupted == 0
    assert not controller._stream_active
    assert "final fragment offered to transport" in caplog.text
    assert "delivery and acknowledgement not observed by delegate" in caplog.text
    assert "producer interrupted" not in caplog.text


def _selected_profile(profile: int) -> bytes:
    """Build a valid recording selection for one advertised profile."""
    u, t = s._u, s.tlv
    container = t((1, b"\0"), (2, t((1, u(4000, 4)))))
    recording = t((1, u(4000, 4)), (2, u(1, 8)), (3, container))
    params = t((1, u(profile, 1)), (2, b"\2"), (3, u(1600, 4)), (4, u(4000, 4)))
    attrs = t((1, u(1280, 2)), (2, u(720, 2)), (3, u(15, 1)))
    video = t((1, b"\0"), (2, params), (3, attrs))
    audio_params = t((1, b"\1"), (2, b"\0"), (3, b"\2"), (4, u(24, 4)))
    return t((1, recording), (2, video), (3, t((1, b"\0"), (2, audio_params))))


async def test_quality_renegotiation_and_legacy_state() -> None:
    """Preserve legacy selections; request one refresh for a profile change."""

    async def source():
        return None

    store = Store()
    baseline = s.b64(_selected_profile(0))
    store.data = {"camera_active": 0, "selected": baseline}
    changed = AsyncMock()
    compatible = c.HKSVController(
        source, "ffmpeg", store, on_capabilities_changed=changed
    )
    compatible.hds = HDS()
    await compatible.start()
    assert compatible.configuration.profile == 0
    assert compatible._selected_value == baseline
    changed.assert_not_awaited()
    assert store.data["recording_profiles"] == [0, 1, 2]
    await compatible.close()

    high = c.HKSVController(
        source, "ffmpeg", store, quality="high", on_capabilities_changed=changed
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
        source, "ffmpeg", store, quality="high", on_capabilities_changed=changed
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
        source, "ffmpeg", store, quality="high", on_capabilities_changed=failed
    )
    controller.hds = HDS()
    await controller.start()
    assert controller._ready
    assert store.data["recording_profiles"] == [0, 1, 2]
    await controller.close()
    changed = AsyncMock()
    restarted = c.HKSVController(
        source, "ffmpeg", store, quality="high", on_capabilities_changed=changed
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

    controller = c.HKSVController(source, "ffmpeg", Store())
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

    controller = c.HKSVController(source, "ffmpeg", Store())
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

    controller = c.HKSVController(source, "ffmpeg", Store())
    process = FailedProcess()
    controller._process = process
    controller._active_copy = (True, True)
    controller._video_copy_disabled = True
    monkeypatch.setattr(c.asyncio, "sleep", AsyncMock())
    controller._schedule_reconcile = lambda: None
    await controller._monitor(process)
    assert controller._video_copy_disabled
    assert not controller._audio_copy_disabled
