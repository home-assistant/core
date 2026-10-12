"""Lifecycle regressions for the existing WAV-to-ffmpeg TTS converter."""

import asyncio
from collections.abc import AsyncGenerator
import contextlib
import io
from pathlib import Path
import sys
from unittest.mock import patch
import wave

import pytest

from homeassistant.components import ffmpeg, tts
from homeassistant.components.tts import SpeechManager
from homeassistant.components.tts.entity import TTSAudioResponse
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component


@pytest.fixture
async def ffmpeg_ready(hass: HomeAssistant) -> HomeAssistant:
    """Set up the real ffmpeg integration without changing the converter."""
    assert await async_setup_component(hass, ffmpeg.DOMAIN, {})
    return hass


@pytest.fixture
def wav_audio() -> bytes:
    """A finite, decodable container, not fabricated raw PCM input."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\x01\x02" * 48000)
    return buffer.getvalue()


async def _observe(task: asyncio.Task, seconds: float = 1.5):
    """Deadline observes without cancelling the operation under test."""
    return await asyncio.wait_for(asyncio.shield(task), seconds)


@pytest.mark.parametrize("output", ["flac", "wav", "mp3"])
async def test_normal_eof_reaps_and_decodes(
    ffmpeg_ready: HomeAssistant, wav_audio: bytes, output: str, tmp_path: Path
) -> None:
    """Normal streaming and file input fully finish and remain decodable."""
    original = asyncio.create_subprocess_exec
    processes = []

    async def spawn(*args, **kwargs):
        process = await original(*args, **kwargs)
        processes.append(process)
        return process

    async def source() -> AsyncGenerator[bytes]:
        yield wav_audio

    with patch("homeassistant.components.tts.asyncio.create_subprocess_exec", spawn):
        for input_audio in (source(), tmp_path / "source.wav"):
            if isinstance(input_audio, Path):
                input_audio.write_bytes(wav_audio)
            encoded = b"".join(
                [
                    chunk
                    async for chunk in tts._async_convert_audio(
                        ffmpeg_ready, "wav", input_audio, output
                    )
                ]
            )
            assert encoded
            decoded = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-loglevel",
                "error",
                "-f",
                output,
                "-i",
                "pipe:0",
                "-f",
                "s16le",
                "pipe:1",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            pcm, stderr = await decoded.communicate(encoded)
            assert decoded.returncode == 0, stderr
            assert len(pcm) >= 30000
    assert len(processes) == 4  # two converters and two independent decoders
    assert all(process.returncode == 0 for process in processes)


async def test_owner_close_stops_held_source_and_reaps(
    ffmpeg_ready: HomeAssistant, wav_audio: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    """A close paused at output must not wait for held later source input."""
    waiting = asyncio.Event()
    held = asyncio.Event()
    closed = asyncio.Event()
    processes = []
    original = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        process = await original(*args, **kwargs)
        processes.append(process)
        return process

    async def source() -> AsyncGenerator[bytes]:
        try:
            yield wav_audio
            waiting.set()
            await held.wait()
            yield wav_audio
        finally:
            closed.set()

    gen = tts._async_convert_audio(ffmpeg_ready, "wav", source(), "wav")
    close_task = None
    try:
        with patch(
            "homeassistant.components.tts.asyncio.create_subprocess_exec", spawn
        ):
            assert await asyncio.wait_for(gen.__anext__(), 3)
            await asyncio.wait_for(waiting.wait(), 3)
            close_task = asyncio.create_task(gen.aclose())
            await _observe(close_task)
            assert closed.is_set()
            assert processes[0].returncode is not None
    finally:
        held.set()  # Harness cleanup only, never before the assertions.
        if close_task is not None:
            await asyncio.wait_for(asyncio.shield(close_task), 5)
        if processes and processes[0].returncode is None:
            processes[0].kill()
        for process in processes:
            await process.wait()
        # Baseline can raise while closing a killed child; final harness close
        # must never hide the behavior assertion above.
        with contextlib.suppress(HomeAssistantError):
            await gen.aclose()


async def test_cancel_blocked_reader_reaps(
    ffmpeg_ready: HomeAssistant, wav_audio: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    """Cancellation retains CancelledError and stops source and child."""
    waiting = asyncio.Event()
    held = asyncio.Event()
    closed = asyncio.Event()
    processes = []
    original = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        process = await original(*args, **kwargs)
        processes.append(process)
        return process

    async def source() -> AsyncGenerator[bytes]:
        try:
            yield wav_audio
            waiting.set()
            await held.wait()
        finally:
            closed.set()

    gen = tts._async_convert_audio(ffmpeg_ready, "wav", source(), "wav")
    task = None
    try:
        with patch(
            "homeassistant.components.tts.asyncio.create_subprocess_exec", spawn
        ):
            assert await asyncio.wait_for(gen.__anext__(), 3)
            await asyncio.wait_for(waiting.wait(), 3)
            task = asyncio.create_task(_collect(gen))
            await asyncio.sleep(0.05)
            assert not task.done()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await _observe(task)
            assert closed.is_set()
            assert processes[0].returncode is not None
    finally:
        held.set()
        if task is not None:
            with contextlib.suppress(asyncio.CancelledError, StopAsyncIteration):
                await asyncio.wait_for(asyncio.shield(task), 5)
        if processes and processes[0].returncode is None:
            processes[0].kill()
        for process in processes:
            await process.wait()
        # Baseline can raise while closing a killed child; final harness close
        # must never hide the behavior assertion above.
        with contextlib.suppress(HomeAssistantError):
            await gen.aclose()


async def test_source_error_surfaces_without_waiting_for_stdout(
    ffmpeg_ready: HomeAssistant, wav_audio: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    """An observed producer failure has priority over child shutdown."""

    class SourceFailed(Exception):
        pass

    async def source() -> AsyncGenerator[bytes]:
        yield wav_audio[:20]
        raise SourceFailed("producer failed")

    original = asyncio.create_subprocess_exec
    processes = []

    async def spawn(*args, **kwargs):
        process = await original(*args, **kwargs)
        processes.append(process)
        return process

    task = None
    try:
        with patch(
            "homeassistant.components.tts.asyncio.create_subprocess_exec", spawn
        ):
            task = asyncio.create_task(
                _collect(tts._async_convert_audio(ffmpeg_ready, "wav", source(), "wav"))
            )
            with pytest.raises(SourceFailed, match="producer failed"):
                await _observe(task)
            assert processes[0].returncode is not None
    finally:
        if processes and processes[0].returncode is None:
            processes[0].kill()
            await processes[0].wait()
        if task is not None:
            with contextlib.suppress(SourceFailed):
                await asyncio.wait_for(task, 5)


async def _collect(gen: AsyncGenerator[bytes]) -> bytes:
    return b"".join([chunk async for chunk in gen])


async def test_invalid_muxer_interrupts_held_source(
    ffmpeg_ready: HomeAssistant, wav_audio: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    """Real ffmpeg fails before a held source finishes, without deadlock."""
    held = asyncio.Event()
    closed = asyncio.Event()
    processes = []
    original = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        process = await original(*args, **kwargs)
        processes.append(process)
        return process

    async def source() -> AsyncGenerator[bytes]:
        try:
            yield wav_audio
            await held.wait()
        finally:
            closed.set()

    task = None
    try:
        with patch(
            "homeassistant.components.tts.asyncio.create_subprocess_exec", spawn
        ):
            task = asyncio.create_task(
                _collect(
                    tts._async_convert_audio(
                        ffmpeg_ready, "wav", source(), "invalid_muxer"
                    )
                )
            )
            with pytest.raises(HomeAssistantError):
                await _observe(task)
            assert closed.is_set()
            assert processes[0].returncode is not None
    finally:
        held.set()
        if task is not None:
            with contextlib.suppress(HomeAssistantError):
                await asyncio.wait_for(task, 5)
        if processes and processes[0].returncode is None:
            processes[0].kill()
            await processes[0].wait()


@pytest.mark.parametrize("exit_code", [0, 7])
async def test_child_exit_while_source_held_is_not_success(
    ffmpeg_ready: HomeAssistant,
    wav_audio: bytes,
    caplog: pytest.LogCaptureFixture,
    exit_code: int,
) -> None:
    """An OS child exit, even zero, must stop a still-held input writer."""
    waiting = asyncio.Event()
    release = asyncio.Event()
    closed = asyncio.Event()
    processes = []
    spawn_os = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        process = await spawn_os(
            "python",
            "-c",
            f"import sys; sys.stderr.write('exit detail'); sys.exit({exit_code})",
            **kwargs,
        )
        processes.append(process)
        return process

    async def source() -> AsyncGenerator[bytes]:
        try:
            yield wav_audio[:100]
            waiting.set()
            await release.wait()
        finally:
            closed.set()

    task = None
    try:
        with patch(
            "homeassistant.components.tts.asyncio.create_subprocess_exec", spawn
        ):
            task = asyncio.create_task(
                _collect(tts._async_convert_audio(ffmpeg_ready, "wav", source(), "wav"))
            )
            await asyncio.wait_for(waiting.wait(), 3)
            with pytest.raises(HomeAssistantError):
                await _observe(task)
            assert closed.is_set()
            assert processes[0].returncode == exit_code
    finally:
        release.set()
        if processes and processes[0].returncode is None:
            processes[0].kill()
        for process in processes:
            await process.wait()
        if task is not None:
            with contextlib.suppress(HomeAssistantError):
                await asyncio.wait_for(asyncio.shield(task), 5)


async def test_large_stderr_is_drained_and_logged_bounded(
    ffmpeg_ready: HomeAssistant,
    wav_audio: bytes,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A full stderr pipe cannot deadlock or retain an unbounded diagnostic."""
    release = asyncio.Event()
    closed = asyncio.Event()
    processes = []
    spawn_os = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        process = await spawn_os(
            "python",
            "-c",
            "import os,sys; os.write(2, b'A'*250000+b'\\xffend'); sys.exit(3)",
            **kwargs,
        )
        processes.append(process)
        return process

    async def source() -> AsyncGenerator[bytes]:
        try:
            yield wav_audio[:100]
            await release.wait()
        finally:
            closed.set()

    task = None
    try:
        with patch(
            "homeassistant.components.tts.asyncio.create_subprocess_exec", spawn
        ):
            task = asyncio.create_task(
                _collect(tts._async_convert_audio(ffmpeg_ready, "wav", source(), "wav"))
            )
            with pytest.raises(HomeAssistantError):
                await _observe(task, 3)
            assert closed.is_set()
            assert processes[0].returncode == 3
            messages = [r.message for r in caplog.records if "end" in r.message]
            assert messages and "end" in messages[-1]
            assert len(messages[-1]) <= 65536 + 100
    finally:
        release.set()
        if processes and processes[0].returncode is None:
            processes[0].kill()
        for process in processes:
            await process.wait()
        if task is not None:
            with contextlib.suppress(HomeAssistantError):
                await asyncio.wait_for(asyncio.shield(task), 5)


async def test_slow_source_finalizer_preserves_cancellation(
    ffmpeg_ready: HomeAssistant,
    wav_audio: bytes,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A five-second cancellable source finalizer is allowed to run out of band."""
    waiting = asyncio.Event()
    release = asyncio.Event()
    entered_finally = asyncio.Event()
    closed = asyncio.Event()
    processes = []
    spawn_os = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        process = await spawn_os(*args, **kwargs)
        processes.append(process)
        return process

    async def source() -> AsyncGenerator[bytes]:
        try:
            yield wav_audio
            waiting.set()
            await release.wait()
        finally:
            entered_finally.set()
            try:
                await asyncio.wait_for(release.wait(), 5)
            finally:
                closed.set()

    gen = tts._async_convert_audio(ffmpeg_ready, "wav", source(), "wav")
    consumer = None
    try:
        with patch(
            "homeassistant.components.tts.asyncio.create_subprocess_exec", spawn
        ):
            assert await asyncio.wait_for(gen.__anext__(), 3)
            await asyncio.wait_for(waiting.wait(), 3)
            consumer = asyncio.create_task(_collect(gen))
            await asyncio.sleep(0.05)
            consumer.cancel()
            with pytest.raises(asyncio.CancelledError):
                await _observe(consumer, 4)
            assert entered_finally.is_set()
            assert processes[0].returncode is not None
    finally:
        release.set()
        if consumer is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(consumer), 6)
        if processes and processes[0].returncode is None:
            processes[0].kill()
        for process in processes:
            await process.wait()
        with contextlib.suppress(HomeAssistantError):
            await gen.aclose()
        await asyncio.wait_for(closed.wait(), 6)


async def test_noncooperative_finalizer_late_error_is_supervised(
    ffmpeg_ready: HomeAssistant,
    wav_audio: bytes,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A source suppressing cancellation cannot block owner or lose late errors."""
    entered = asyncio.Event()
    release = asyncio.Event()
    processes = []
    spawn_os = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        process = await spawn_os(*args, **kwargs)
        processes.append(process)
        return process

    async def source() -> AsyncGenerator[bytes]:
        yield wav_audio
        entered.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            await release.wait()
            raise RuntimeError("late source failure") from None

    gen = tts._async_convert_audio(ffmpeg_ready, "wav", source(), "wav")
    close_task = None
    try:
        with patch(
            "homeassistant.components.tts.asyncio.create_subprocess_exec", spawn
        ):
            assert await asyncio.wait_for(gen.__anext__(), 3)
            await asyncio.wait_for(entered.wait(), 3)
            close_task = asyncio.create_task(gen.aclose())
            await _observe(close_task, 4)
            assert processes[0].returncode is not None
            assert any("did not stop promptly" in r.message for r in caplog.records)
            release.set()
            await asyncio.sleep(0.1)
            assert any("late source failure" in r.message for r in caplog.records)
    finally:
        release.set()
        if close_task is not None:
            await asyncio.wait_for(asyncio.shield(close_task), 6)
        if processes and processes[0].returncode is None:
            processes[0].kill()
        for process in processes:
            await process.wait()
        with contextlib.suppress(HomeAssistantError):
            await gen.aclose()


async def test_observed_source_error_survives_failing_close(
    ffmpeg_ready: HomeAssistant, wav_audio: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    """The writer's observed source error outranks its later close exception."""

    class ReadFailed(Exception):
        pass

    class CloseFailed(Exception):
        pass

    class Source(AsyncGenerator[bytes]):
        def __init__(self) -> None:
            self.read = False
            self.closed = False

        async def asend(self, value) -> bytes:  # codespell:ignore asend
            if not self.read:
                self.read = True
                return wav_audio[:20]
            raise ReadFailed("observed read failure")

        async def __anext__(self) -> bytes:
            return await self.asend(None)  # codespell:ignore asend

        async def athrow(self, *args) -> bytes:
            raise NotImplementedError

        async def aclose(self) -> None:
            self.closed = True
            raise CloseFailed("secondary close failure")

    source = Source()
    processes = []
    spawn_os = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        process = await spawn_os(*args, **kwargs)
        processes.append(process)
        return process

    task = None
    try:
        with patch(
            "homeassistant.components.tts.asyncio.create_subprocess_exec", spawn
        ):
            task = asyncio.create_task(
                _collect(tts._async_convert_audio(ffmpeg_ready, "wav", source, "wav"))
            )
            with pytest.raises(ReadFailed, match="observed read failure"):
                await _observe(task)
            assert source.closed
            assert processes[0].returncode is not None
    finally:
        if processes and processes[0].returncode is None:
            processes[0].kill()
        for process in processes:
            await process.wait()
        if task is not None:
            with contextlib.suppress(ReadFailed, CloseFailed):
                await asyncio.wait_for(asyncio.shield(task), 5)


async def test_manager_converted_wrapper_forwards_close(
    ffmpeg_ready: HomeAssistant, wav_audio: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    """Closing the public manager's converted generator reaches its child."""
    held = asyncio.Event()
    waiting = asyncio.Event()
    closed = asyncio.Event()
    processes = []
    spawn_os = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        process = await spawn_os(*args, **kwargs)
        processes.append(process)
        return process

    async def source() -> AsyncGenerator[bytes]:
        try:
            yield wav_audio
            waiting.set()
            await held.wait()
        finally:
            closed.set()

    class Engine:
        name = "fixture"
        supported_options = []

        def async_supports_streaming_input(self):
            return True

        async def internal_async_stream_tts_audio(self, request):
            return TTSAudioResponse("wav", source())

    manager = SpeechManager(ffmpeg_ready, False, "", 0)
    gen = manager._async_generate_tts_audio(
        Engine(),
        "hello",
        "en",
        {tts.ATTR_PREFERRED_FORMAT: "wav", tts.ATTR_PREFERRED_SAMPLE_RATE: 16000},
    )
    close_task = None
    try:
        with patch(
            "homeassistant.components.tts.asyncio.create_subprocess_exec", spawn
        ):
            assert await asyncio.wait_for(gen.__anext__(), 3)
            await asyncio.wait_for(waiting.wait(), 3)
            close_task = asyncio.create_task(gen.aclose())
            await _observe(close_task, 3)
            assert closed.is_set()
            assert processes[0].returncode is not None
    finally:
        held.set()
        if close_task is not None:
            await asyncio.wait_for(asyncio.shield(close_task), 5)
        if processes and processes[0].returncode is None:
            processes[0].kill()
        for process in processes:
            await process.wait()
        with contextlib.suppress(HomeAssistantError):
            await gen.aclose()


class _ExhaustedSource(AsyncGenerator[bytes]):
    """Separate input exhaustion from an independently delayed source close."""

    def __init__(self, delay: float, fails: bool = False) -> None:
        self.pulled = False
        self.close_entered = asyncio.Event()
        self.closed = asyncio.Event()
        self.delay = delay
        self.fails = fails

    async def asend(self, value) -> bytes:  # codespell:ignore asend
        if self.pulled:
            raise StopAsyncIteration
        self.pulled = True
        return b"R" * 100  # OS substitute, not a WAV decoding claim.

    async def __anext__(self) -> bytes:
        return await self.asend(None)  # codespell:ignore asend

    async def athrow(self, *args) -> bytes:
        raise NotImplementedError

    async def aclose(self) -> None:
        self.close_entered.set()
        try:
            await asyncio.sleep(self.delay)
            if self.fails:
                raise RuntimeError("secondary close failure")
        finally:
            self.closed.set()


@pytest.mark.parametrize(("delayed_close", "fails"), [(2.5, False), (0.05, True)])
async def test_failed_child_during_exhausted_source_close_is_primary(
    ffmpeg_ready: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    delayed_close: float,
    fails: bool,
) -> None:
    """Known nonzero child failure must not await or inherit source finalization."""
    source = _ExhaustedSource(delayed_close, fails)
    original = asyncio.create_subprocess_exec
    processes = []

    async def spawn(*args, **kwargs):
        process = await original(
            sys.executable,
            "-c",
            "import os,sys;os.write(2,b'failure detail\\n');sys.exit(7)",
            **kwargs,
        )
        processes.append(process)
        return process

    owner = None
    try:
        with patch(
            "homeassistant.components.tts.asyncio.create_subprocess_exec", spawn
        ):
            owner = asyncio.create_task(
                _collect(tts._async_convert_audio(ffmpeg_ready, "wav", source, "wav"))
            )
            await asyncio.wait_for(source.close_entered.wait(), 3)
            with pytest.raises(
                HomeAssistantError, match="Unexpected error while running ffmpeg"
            ):
                await _observe(owner, 1.5)
            assert processes[0].returncode == 7
            assert source.closed.is_set()
            assert any("failure detail" in record.message for record in caplog.records)
    finally:
        if owner is not None and not owner.done():
            owner.cancel()
        for process in processes:
            if process.returncode is None:
                process.kill()
            await asyncio.wait_for(process.wait(), 5)
        if owner is not None:
            await asyncio.gather(owner, return_exceptions=True)
        await asyncio.wait_for(source.closed.wait(), 5)


async def test_normal_child_exit_waits_for_exhausted_source_close(
    ffmpeg_ready: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Input exhaustion with a slow close is not an early-exit failure."""
    source = _ExhaustedSource(0.2)
    original = asyncio.create_subprocess_exec
    processes = []

    async def spawn(*args, **kwargs):
        process = await original(
            sys.executable, "-c", "import sys;sys.exit(0)", **kwargs
        )
        processes.append(process)
        return process

    try:
        with patch(
            "homeassistant.components.tts.asyncio.create_subprocess_exec", spawn
        ):
            assert (
                await asyncio.wait_for(
                    _collect(
                        tts._async_convert_audio(ffmpeg_ready, "wav", source, "wav")
                    ),
                    3,
                )
                == b""
            )
            assert source.close_entered.is_set() and source.closed.is_set()
            assert processes[0].returncode == 0
    finally:
        for process in processes:
            if process.returncode is None:
                process.kill()
            await asyncio.wait_for(process.wait(), 5)


@pytest.mark.parametrize("generator_input", [False, True], ids=["path", "exhausted"])
@pytest.mark.parametrize("exit_code", [0, 7])
async def test_stdout_eof_precedes_delayed_normal_child_exit(
    ffmpeg_ready: HomeAssistant,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    generator_input: bool,
    exit_code: int,
) -> None:
    """Reap a child after EOF, not before its delayed exit code is known."""
    marker = tmp_path / "stdout-closed"
    source = _ExhaustedSource(0)
    payload = b"normal-output"
    script = (
        "import os,sys,time,pathlib;"
        "data=sys.stdin.buffer.read() if 'pipe:0' in sys.argv else b'';"
        "assert data == (b'R'*100 if 'pipe:0' in sys.argv else b'');"
        f"os.write(1,{payload!r});os.close(1);"
        f"pathlib.Path({str(marker)!r}).touch();"
        "os.write(2,b'late exit detail\\n');"
        "time.sleep(0.25);"
        f"sys.exit({exit_code})"
    )
    # The substitute consumes generator stdin before closing stdout. It ignores
    # the requested input path, which is deliberately not an ffmpeg claim.
    original = asyncio.create_subprocess_exec
    processes = []

    async def spawn(*args, **kwargs):
        process = await original(sys.executable, "-c", script, *args[1:], **kwargs)
        processes.append(process)
        return process

    async def wait_for_marker() -> None:
        while not marker.exists():
            await asyncio.sleep(0.005)

    owner = None
    try:
        with patch(
            "homeassistant.components.tts.asyncio.create_subprocess_exec", spawn
        ):
            audio_input = source if generator_input else tmp_path / "source.wav"
            owner = asyncio.create_task(
                _collect(
                    tts._async_convert_audio(ffmpeg_ready, "wav", audio_input, "wav")
                )
            )
            await asyncio.wait_for(wait_for_marker(), 3)
            if generator_input:
                await asyncio.wait_for(source.close_entered.wait(), 3)
            assert not owner.done()  # stdout is shut; process still owes an exit.
            if exit_code:
                with pytest.raises(
                    HomeAssistantError, match="Unexpected error while running ffmpeg"
                ):
                    await _observe(owner, 3)
                assert any("late exit detail" in r.message for r in caplog.records)
            else:
                assert await _observe(owner, 3) == payload
            assert processes[0].returncode == exit_code
            if generator_input:
                assert source.closed.is_set()
            assert not any(
                task.get_name().startswith("tts_ffmpeg") and not task.done()
                for task in asyncio.all_tasks()
            )
    finally:
        for process in processes:
            if process.returncode is None:
                process.kill()
            await asyncio.wait_for(process.wait(), 5)
        if owner is not None:
            if not owner.done():
                owner.cancel()
            await asyncio.gather(owner, return_exceptions=True)


async def test_cancel_during_normal_exit_wait_reaps_child(
    ffmpeg_ready: HomeAssistant,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Cancellation during EOF-to-exit wait owns and reaps the child."""
    marker = tmp_path / "stdout-closed"
    release = tmp_path / "release-exit"
    script = (
        "import os,time,pathlib;"
        "os.write(1,b'prefix');os.close(1);"
        f"pathlib.Path({str(marker)!r}).touch()\n"
        f"while not pathlib.Path({str(release)!r}).exists():time.sleep(0.01)"
    )
    original = asyncio.create_subprocess_exec
    processes = []

    async def spawn(*args, **kwargs):
        process = await original(sys.executable, "-c", script, **kwargs)
        processes.append(process)
        return process

    async def wait_for_marker() -> None:
        while not marker.exists():
            await asyncio.sleep(0.005)

    owner = None
    try:
        with patch(
            "homeassistant.components.tts.asyncio.create_subprocess_exec", spawn
        ):
            owner = asyncio.create_task(
                _collect(
                    tts._async_convert_audio(
                        ffmpeg_ready, "wav", tmp_path / "source.wav", "wav"
                    )
                )
            )
            await asyncio.wait_for(wait_for_marker(), 3)
            await asyncio.sleep(0.15)
            assert not owner.done()
            owner.cancel()
            with pytest.raises(asyncio.CancelledError):
                await _observe(owner, 3)
            assert processes[0].returncode is not None
            assert not any(
                task.get_name().startswith("tts_ffmpeg") and not task.done()
                for task in asyncio.all_tasks()
            )
    finally:
        release.touch()
        for process in processes:
            if process.returncode is None:
                process.kill()
            await asyncio.wait_for(process.wait(), 5)
        if owner is not None:
            if not owner.done():
                owner.cancel()
            await asyncio.gather(owner, return_exceptions=True)


async def test_stdout_eof_before_child_exit_interrupts_source_and_reaps(
    ffmpeg_ready: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Stdout can close while stderr and the child remain open."""
    entered = asyncio.Event()
    release = asyncio.Event()
    closed = asyncio.Event()
    processes = []
    original = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        process = await original(
            sys.executable,
            "-c",
            "import os,time;os.close(1);os.write(2,b'closed\\n');time.sleep(30)",
            **kwargs,
        )
        processes.append(process)
        return process

    async def source() -> AsyncGenerator[bytes]:
        try:
            yield b"R" * 100  # Deliberate OS stress, not valid WAV audio.
            entered.set()
            await release.wait()
        finally:
            closed.set()

    owner = None
    try:
        with patch(
            "homeassistant.components.tts.asyncio.create_subprocess_exec", spawn
        ):
            owner = asyncio.create_task(
                _collect(tts._async_convert_audio(ffmpeg_ready, "wav", source(), "wav"))
            )
            await asyncio.wait_for(entered.wait(), 3)
            with pytest.raises(
                HomeAssistantError, match="before TTS input was exhausted"
            ):
                await _observe(owner, 1.5)
            assert closed.is_set()
            assert processes[0].returncode is not None
    finally:
        release.set()
        if owner is not None and not owner.done():
            owner.cancel()
        for process in processes:
            if process.returncode is None:
                process.kill()
            await asyncio.wait_for(process.wait(), 5)
        if owner is not None:
            await asyncio.gather(owner, return_exceptions=True)
