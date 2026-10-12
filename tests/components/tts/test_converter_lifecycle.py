"""Lifecycle regressions for the existing WAV-to-ffmpeg TTS converter."""

import asyncio
from collections.abc import AsyncGenerator
import contextlib
import io
from pathlib import Path
import sys
from types import SimpleNamespace
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
    assert not any(
        task.get_name() == "tts_ffmpeg_source_failure" and not task.done()
        for task in asyncio.all_tasks()
    )


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
            sys.executable,
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
            sys.executable,
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


async def test_exhausted_source_close_error_is_propagated(
    ffmpeg_ready: HomeAssistant,
) -> None:
    """A close failure after normal source EOF is not silently discarded."""
    failure = RuntimeError("normal EOF close failed")

    class Source(AsyncGenerator[bytes]):
        def __init__(self) -> None:
            self.pulls = 0
            self.closed = False

        async def asend(self, value) -> bytes:  # codespell:ignore asend
            self.pulls += 1
            if self.pulls == 1:
                return b"R" * 32  # OS ownership substitute, not valid WAV.
            raise StopAsyncIteration

        async def __anext__(self) -> bytes:
            return await self.asend(None)  # codespell:ignore asend

        async def athrow(self, *args) -> bytes:
            raise NotImplementedError

        async def aclose(self) -> None:
            self.closed = True
            raise failure

    source = Source()
    processes = []
    spawn_os = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        process = await spawn_os(
            sys.executable, "-c", "import sys;sys.stdin.buffer.read()", **kwargs
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
            with pytest.raises(RuntimeError) as caught:
                await _observe(owner, 3)
            assert caught.value is failure
            assert source.pulls == 2
            assert source.closed
            assert processes[0].returncode == 0
            assert not any(
                task.get_name()
                in (
                    "tts_ffmpeg_source_failure",
                    "tts_ffmpeg_stdin_failure",
                    "tts_ffmpeg_stdout",
                    "tts_ffmpeg_wait",
                    "tts_ffmpeg_stderr",
                )
                and not task.done()
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


@pytest.mark.parametrize("mode", ["held", "suppress_cancel", "cooperative", "eager"])
async def test_source_pull_failure_wakes_blocked_owner_before_close(
    ffmpeg_ready: HomeAssistant, mode: str
) -> None:
    """An observed pull error wakes an existing wait without its writer finalizer."""

    class PullFailed(Exception):
        pass

    class Source(AsyncGenerator[bytes]):
        def __init__(self) -> None:
            self.error = PullFailed("observed source failure")
            self.pulls = 0
            self.pulling = asyncio.Event()
            self.fail = asyncio.Event()
            self.closing = asyncio.Event()
            self.release_close = asyncio.Event()
            self.closed = asyncio.Event()

        async def asend(self, value) -> bytes:  # codespell:ignore asend
            self.pulls += 1
            if self.pulls == 1 and mode != "eager":
                return b"R" * 32  # Child is an OS substitute, not a WAV decoder.
            self.pulling.set()
            if mode != "eager":
                await self.fail.wait()
            raise self.error

        async def __anext__(self) -> bytes:
            return await self.asend(None)  # codespell:ignore asend

        async def athrow(self, *args) -> bytes:
            raise NotImplementedError

        async def aclose(self) -> None:
            self.closing.set()
            if mode in ("held", "suppress_cancel"):
                try:
                    await self.release_close.wait()
                except asyncio.CancelledError:
                    if mode != "suppress_cancel":
                        raise
                    await self.release_close.wait()
            self.closed.set()

    source = Source()
    processes = []
    stdout_read_started = asyncio.Event()
    spawn_os = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        # Keep stdout and process exit pending while the source fails.
        process = await spawn_os(
            sys.executable, "-c", "import time;time.sleep(30)", **kwargs
        )
        assert process.stdout is not None
        read = process.stdout.read

        async def observed_read(n: int = -1) -> bytes:
            stdout_read_started.set()
            return await read(n)

        process.stdout.read = observed_read
        processes.append(process)
        return process

    gen = tts._async_convert_audio(ffmpeg_ready, "wav", source, "wav")
    owner = None
    try:
        with (
            patch(
                "homeassistant.components.tts.ffmpeg.get_ffmpeg_manager",
                return_value=SimpleNamespace(binary="unused-os-substitute"),
            ),
            patch("homeassistant.components.tts.asyncio.create_subprocess_exec", spawn),
        ):
            owner = asyncio.create_task(anext(gen))
            await asyncio.wait_for(source.pulling.wait(), 3)
            if mode != "eager":
                # The controlled child keeps stdout open without writing. An
                # entered real pipe read establishes the owner's pending output
                # operation while the source pull is still held by the fixture.
                await asyncio.wait_for(stdout_read_started.wait(), 3)
                assert processes[0].returncode is None
                assert not owner.done()
                source.fail.set()
            await asyncio.wait_for(source.closing.wait(), 3)
            assert processes[0].returncode is None
            if mode in ("held", "suppress_cancel"):
                assert not source.release_close.is_set()
            with pytest.raises(PullFailed) as raised:
                await _observe(owner, 1.5)
            assert raised.value is source.error
            assert processes[0].returncode is not None
            assert not any(
                task.get_name() == "tts_ffmpeg_source_failure" and not task.done()
                for task in asyncio.all_tasks()
            )
            assert not source.release_close.is_set()
            if mode == "cooperative":
                assert source.closed.is_set()
            if mode in ("held", "suppress_cancel"):
                assert not source.closed.is_set()
    finally:
        source.fail.set()
        source.release_close.set()  # Harness release after outcome/reap assertions.
        if processes and processes[0].returncode is None:
            processes[0].kill()
        for process in processes:
            await asyncio.wait_for(process.wait(), 5)
        if owner is not None:
            if not owner.done():
                owner.cancel()
            await asyncio.gather(owner, return_exceptions=True)
        await gen.aclose()


@pytest.mark.parametrize("boundary", ["public", "inner"])
async def test_converted_override_close_reaps_live_ffmpeg(
    ffmpeg_ready: HomeAssistant, tmp_path: Path, boundary: str
) -> None:
    """Each override owner forwards close to its real, still-live converter."""
    input_path = tmp_path / "long.wav"
    with wave.open(str(input_path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\x01\x02" * (16000 * 120))

    manager = SimpleNamespace(
        token_to_stream={},
        token_to_stream_cleanup=SimpleNamespace(schedule=lambda: None),
    )
    stream = tts.ResultStream(
        hass=ffmpeg_ready,
        token="override-close",
        extension="wav",
        content_type="audio/wav",
        engine="fixture",
        use_file_cache=False,
        language="en",
        options={tts.ATTR_PREFERRED_FORMAT: "wav"},
        supports_streaming_input=False,
        _manager=manager,
    )
    stream.async_override_result(input_path)
    spawn_os = asyncio.create_subprocess_exec
    convert = tts._async_convert_audio
    get_inner = tts.ResultStream._async_stream_override_result
    processes = []
    converters = []
    inners = []
    public = None

    async def spawn(*args, **kwargs):
        process = await spawn_os(*args, **kwargs)
        processes.append(process)
        return process

    def track_convert(*args, **kwargs):
        converter = convert(*args, **kwargs)
        converters.append(converter)
        return converter

    def track_inner(self):
        inner = get_inner(self)
        inners.append(inner)
        return inner

    try:
        with (
            patch("homeassistant.components.tts.asyncio.create_subprocess_exec", spawn),
            patch("homeassistant.components.tts._async_convert_audio", track_convert),
            patch.object(
                tts.ResultStream, "_async_stream_override_result", track_inner
            ),
        ):
            public = stream.async_stream_result()
            gen = (
                public
                if boundary == "public"
                else stream._async_stream_override_result()
            )
            assert (await asyncio.wait_for(anext(gen), 5)).startswith(b"RIFF")
            assert len(processes) == len(converters) == 1
            assert processes[0].returncode is None  # Actual OS child still alive.
            await asyncio.wait_for(gen.aclose(), 3)
            assert processes[0].returncode is not None  # Before harness cleanup.
            assert converters[0].ag_frame is None
            if boundary == "public":
                assert len(inners) == 1 and inners[0].ag_frame is None
    finally:
        for process in processes:
            if process.returncode is None:
                process.kill()
            await asyncio.wait_for(process.wait(), 5)
        for generator in (public, *inners, *converters):
            if generator is not None:
                await generator.aclose()


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


@pytest.mark.parametrize("failure", [BrokenPipeError, ConnectionResetError])
async def test_stdin_transport_failure_keeps_child_diagnostic(
    ffmpeg_ready: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    failure: type[OSError],
) -> None:
    """A failed large stdin write cannot hide the real child's failed exit."""
    original = asyncio.create_subprocess_exec
    processes = []
    source_closed = asyncio.Event()

    async def spawn(*args, **kwargs):
        process = await original(
            sys.executable,
            "-c",
            "import os,sys;os.read(0,1);os.write(2,b'child pipe detail\\n');sys.exit(7)",
            **kwargs,
        )
        processes.append(process)
        assert process.stdin is not None
        if failure is ConnectionResetError:
            # The OS normally raises BrokenPipeError here. Exercise the other
            # real StreamWriter transport failure at the same drain boundary.
            original_drain = process.stdin.drain

            async def reset_after_drain():
                try:
                    await original_drain()
                except BrokenPipeError as err:
                    raise ConnectionResetError("stdin reset") from err

            process.stdin.drain = reset_after_drain
        return process

    async def source() -> AsyncGenerator[bytes]:
        try:
            yield b"R" * (8 * 1024 * 1024)
        finally:
            source_closed.set()

    owner = None
    try:
        with patch(
            "homeassistant.components.tts.asyncio.create_subprocess_exec", spawn
        ):
            owner = asyncio.create_task(
                _collect(tts._async_convert_audio(ffmpeg_ready, "wav", source(), "wav"))
            )
            with pytest.raises(
                HomeAssistantError, match="Unexpected error while running ffmpeg"
            ):
                await _observe(owner, 4)
            assert processes[0].returncode == 7
            assert source_closed.is_set()
            assert any("child pipe detail" in r.message for r in caplog.records)
    finally:
        for process in processes:
            if process.returncode is None:
                process.kill()
            await asyncio.wait_for(process.wait(), 5)
        if owner is not None:
            if not owner.done():
                owner.cancel()
            await asyncio.gather(owner, return_exceptions=True)


@pytest.mark.parametrize("exit_code", [None, 7], ids=["live-child", "failed-child"])
async def test_known_stdin_failure_before_next_output_pull(
    ffmpeg_ready: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    exit_code: int | None,
) -> None:
    """A paused consumer notices a real pipe failure before reading stdout again."""
    release_child = tmp_path / "close-stdin"
    finalizer_entered = asyncio.Event()
    release_finalizer = asyncio.Event()
    transport_failed = asyncio.Event()
    transport_errors: list[BrokenPipeError] = []
    processes = []
    spawn_os = asyncio.create_subprocess_exec
    script = (
        "import os,sys,time\n"
        "os.write(1,b'PREFIX')\n"
        "while not os.path.exists(sys.argv[1]):time.sleep(.01)\n"
        "os.close(0)\n"
        + (
            "os.write(2,b'prepull child failure\\n');sys.exit(7)"
            if exit_code is not None
            else "time.sleep(30)"
        )
    )

    async def spawn(*args, **kwargs):
        process = await spawn_os(
            sys.executable, "-c", script, str(release_child), **kwargs
        )
        processes.append(process)
        assert process.stdin is not None
        drain = process.stdin.drain

        async def observe_drain():
            try:
                await drain()
            except BrokenPipeError as err:
                transport_errors.append(err)
                transport_failed.set()
                raise

        process.stdin.drain = observe_drain
        return process

    async def source() -> AsyncGenerator[bytes]:
        try:
            yield b"R" * (8 * 1024 * 1024)  # Real pipe pressure; not valid WAV.
        finally:
            finalizer_entered.set()
            try:
                await release_finalizer.wait()
            except asyncio.CancelledError:
                await release_finalizer.wait()

    gen = tts._async_convert_audio(ffmpeg_ready, "wav", source(), "wav")
    owner = None
    try:
        with patch(
            "homeassistant.components.tts.asyncio.create_subprocess_exec", spawn
        ):
            assert await asyncio.wait_for(gen.__anext__(), 3) == b"PREFIX"
            # The converter is suspended at its yield: the next read cannot
            # start until the consumer demands it. Fail the actual OS pipe now.
            release_child.touch()
            await asyncio.wait_for(finalizer_entered.wait(), 3)
            assert transport_failed.is_set()
            assert not release_finalizer.is_set()
            if exit_code is None:
                assert processes[0].returncode is None
            else:
                assert await asyncio.wait_for(processes[0].wait(), 3) == 7
            owner = asyncio.create_task(gen.__anext__())
            if exit_code is None:
                with pytest.raises(BrokenPipeError) as caught:
                    await _observe(owner, 3)
                assert caught.value is transport_errors[0]
            else:
                with pytest.raises(
                    HomeAssistantError, match="Unexpected error while running ffmpeg"
                ):
                    await _observe(owner, 3)
                assert any(
                    "prepull child failure" in record.message
                    for record in caplog.records
                )
            assert processes[0].returncode is not None
            assert not release_finalizer.is_set()
            assert not any(
                task.get_name()
                in (
                    "tts_ffmpeg_source_failure",
                    "tts_ffmpeg_stdin_failure",
                    "tts_ffmpeg_stdout",
                    "tts_ffmpeg_wait",
                    "tts_ffmpeg_stderr",
                )
                and not task.done()
                for task in asyncio.all_tasks()
            )
    finally:
        release_child.touch()
        if owner is not None and not owner.done():
            owner.cancel()
        for process in processes:
            if process.returncode is None:
                process.kill()
            await asyncio.wait_for(process.wait(), 5)
        release_finalizer.set()
        if owner is not None:
            await asyncio.wait_for(asyncio.gather(owner, return_exceptions=True), 5)
        with contextlib.suppress(BrokenPipeError, HomeAssistantError):
            await gen.aclose()


@pytest.mark.parametrize("exit_code", [None, 7], ids=["live-child", "known-exit"])
async def test_broken_stdin_reaps_before_held_source_finalizer_finishes(
    ffmpeg_ready: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    exit_code: int | None,
) -> None:
    """Observe an OS pipe failure without waiting for the writer's held close."""
    release_finalizer = asyncio.Event()
    finalizer_entered = asyncio.Event()
    transport_failed = asyncio.Event()
    transport_errors: list[BrokenPipeError] = []
    processes = []
    spawn_os = asyncio.create_subprocess_exec
    script = (
        "import os,time,sys;os.close(0);"
        "os.write(2,b'held-finalizer child failure\\n');sys.exit(7)"
        if exit_code is not None
        else "import os,time;os.close(0);time.sleep(30)"
    )

    async def spawn(*args, **kwargs):
        process = await spawn_os(sys.executable, "-c", script, **kwargs)
        processes.append(process)
        assert process.stdin is not None
        drain = process.stdin.drain

        async def observe_drain():
            try:
                await drain()
            except BrokenPipeError as err:
                transport_errors.append(err)
                transport_failed.set()
                if exit_code is not None:
                    # Deliver the actual drain exception only once the real
                    # child has exited; the live-child case remains unblocked.
                    assert await asyncio.wait_for(process.wait(), 3) == 7
                raise

        process.stdin.drain = observe_drain
        return process

    async def source() -> AsyncGenerator[bytes]:
        try:
            yield b"R" * (8 * 1024 * 1024)  # Force real OS pipe pressure.
        finally:
            finalizer_entered.set()
            try:
                await release_finalizer.wait()
            except asyncio.CancelledError:
                # A slow close can continue under bounded supervision.
                await release_finalizer.wait()

    owner = None
    try:
        with patch(
            "homeassistant.components.tts.asyncio.create_subprocess_exec", spawn
        ):
            owner = asyncio.create_task(
                _collect(tts._async_convert_audio(ffmpeg_ready, "wav", source(), "wav"))
            )
            await asyncio.wait_for(finalizer_entered.wait(), 3)
            assert transport_failed.is_set()  # Real StreamWriter.drain raised.
            assert len(transport_errors) == 1
            # Observation never cancels the owner, child or source. These
            # assertions happen before any harness release/kill/cancellation.
            if exit_code is None:
                with pytest.raises(BrokenPipeError) as caught:
                    await _observe(owner, 3)
                assert caught.value is transport_errors[0]
                assert processes[0].returncode is not None
            else:
                with pytest.raises(
                    HomeAssistantError, match="Unexpected error while running ffmpeg"
                ):
                    await _observe(owner, 3)
                assert processes[0].returncode == 7
                assert any(
                    "held-finalizer child failure" in record.message
                    for record in caplog.records
                )
            assert finalizer_entered.is_set()
            assert not release_finalizer.is_set()
    finally:
        # Harness cleanup only after the observable outcome and reaping checks.
        if owner is not None and not owner.done():
            owner.cancel()
        for process in processes:
            if process.returncode is None:
                process.kill()
            await asyncio.wait_for(process.wait(), 5)
        release_finalizer.set()
        if owner is not None:
            await asyncio.wait_for(asyncio.gather(owner, return_exceptions=True), 5)


@pytest.mark.parametrize("paused", [False, True], ids=["eager", "paused-yield"])
async def test_completed_writer_source_error_interrupts_held_child(
    ffmpeg_ready: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    paused: bool,
) -> None:
    """An already failed writer must wake the reader without stdout or exit."""

    class SourceFailed(Exception):
        pass

    failure = SourceFailed("source failed while child held")
    allow_failure = asyncio.Event()
    source_closed = asyncio.Event()
    original = asyncio.create_subprocess_exec
    processes = []

    async def spawn(*args, **kwargs):
        script = (
            "import os,time;os.write(1,b'PREFIX');time.sleep(30)"
            if paused
            else "import time;time.sleep(30)"
        )
        process = await original(
            sys.executable,
            "-c",
            script,
            **kwargs,
        )
        processes.append(process)
        return process

    async def source() -> AsyncGenerator[bytes]:
        try:
            if paused:
                yield b"R" * 100
                await allow_failure.wait()
            raise failure
        finally:
            source_closed.set()

    gen = tts._async_convert_audio(ffmpeg_ready, "wav", source(), "wav")
    owner = None
    try:
        with patch(
            "homeassistant.components.tts.asyncio.create_subprocess_exec", spawn
        ):
            if paused:
                assert await asyncio.wait_for(gen.__anext__(), 3) == b"PREFIX"
                allow_failure.set()
                await asyncio.wait_for(source_closed.wait(), 3)
            owner = asyncio.create_task(gen.__anext__())
            with pytest.raises(SourceFailed) as caught:
                await _observe(owner, 1.5)
            assert caught.value is failure
            assert processes[0].returncode is not None
            assert source_closed.is_set()
    finally:
        allow_failure.set()
        for process in processes:
            if process.returncode is None:
                process.kill()
            await asyncio.wait_for(process.wait(), 5)
        if owner is not None:
            if not owner.done():
                owner.cancel()
            await asyncio.gather(owner, return_exceptions=True)
        with contextlib.suppress(SourceFailed, HomeAssistantError):
            await gen.aclose()


async def test_provider_transport_class_error_remains_primary(
    ffmpeg_ready: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A producer's BrokenPipeError is not a subprocess stdin failure."""
    failure = BrokenPipeError("provider's own broken pipe")
    original = asyncio.create_subprocess_exec
    processes = []

    async def spawn(*args, **kwargs):
        process = await original(*args, **kwargs)
        processes.append(process)
        return process

    async def source() -> AsyncGenerator[bytes]:
        if failure is not None:
            raise failure
        yield b""

    owner = None
    try:
        with patch(
            "homeassistant.components.tts.asyncio.create_subprocess_exec", spawn
        ):
            owner = asyncio.create_task(
                _collect(tts._async_convert_audio(ffmpeg_ready, "wav", source(), "wav"))
            )
            with pytest.raises(BrokenPipeError) as caught:
                await _observe(owner)
            assert caught.value is failure
            assert processes[0].returncode is not None
    finally:
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
                HomeAssistantError,
                match="ffmpeg output closed before TTS input was exhausted",
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
