"""A fake Voice app for run tests: its websocket and the messages it sends."""

import asyncio
import json
from typing import Any

import aiohttp

type Answer = dict[str, Any] | aiohttp.WSMessage | Exception | None
"""What the app says: JSON, a ready-made message, an error reading, or None
for going away."""


def accepted(wake_word_audio_ms: int) -> dict[str, Any]:
    """What the app says for a wake word it heard."""
    return {
        "type": "wake-word-end",
        "wake_word_output": {"wake_word_audio_ms": wake_word_audio_ms},
    }


def rejected(reason: str | None = None) -> dict[str, Any]:
    """What the app says for a wake word it did not hear."""
    output = {} if reason is None else {"reason": reason}
    return {"type": "wake-word-rejected", "wake_word_output": output}


def speech_started(timestamp_ms: int) -> dict[str, Any]:
    """What the app says when the command begins."""
    return {"type": "stt-vad-start", "timestamp": timestamp_ms}


def speech_ended(timestamp_ms: int) -> dict[str, Any]:
    """What the app says when the command is over."""
    return {"type": "stt-vad-end", "timestamp": timestamp_ms}


class FakeWebsocket:
    """The app's end of a run: says what the test wrote down, when it said so.

    Each answer comes once that many chunks of audio have reached the app.
    """

    def __init__(self, answers: list[tuple[int, Answer]] | None = None) -> None:
        """Set up the app's end with its answers scripted."""
        self.audio = bytearray()
        self.run_start: dict[str, Any] | None = None
        self.chunks = 0
        self.audio_ended = False
        self.closed = False
        self.unreachable = False
        """Make every send fail, as it does once the app has fallen over."""
        self.stalled = False
        """Make every send hang, as it does once the app stops reading."""
        self._answers = list(answers or [])
        self._messages: asyncio.Queue[Answer] = asyncio.Queue()
        self._say_what_is_due()

    def _say_what_is_due(self) -> None:
        while self._answers and (self._answers[0][0] <= self.chunks):
            self._messages.put_nowait(self._answers.pop(0)[1])

    def queue_answer(self, answer: Answer) -> None:
        """Queue a response from the app."""
        self._messages.put_nowait(answer)

    def go_away(self) -> None:
        """Stop saying anything, as an app that fell over does."""
        self._messages.put_nowait(None)

    async def send_bytes(self, data: bytes) -> None:
        """Take the next of the run's audio."""
        if self.unreachable:
            raise aiohttp.ClientConnectionError("gone")
        if self.stalled:
            await asyncio.Event().wait()
        self.audio.extend(data)
        self.chunks += 1
        self._say_what_is_due()
        # Let the run read what was said before the next chunk goes in
        await asyncio.sleep(0)

    async def send_json(self, data: dict[str, Any]) -> None:
        """Take the start of the run, or the end of the audio."""
        if self.unreachable:
            raise aiohttp.ClientConnectionError("gone")
        if data["type"] == "run-start":
            self.run_start = data
            return
        assert data == {"type": "audio-end"}
        self.audio_ended = True

    async def close(self) -> None:
        """Let the run go."""
        self.closed = True
        self._messages.put_nowait(None)

    def __aiter__(self) -> FakeWebsocket:
        """Iterate over the app's answers."""
        return self

    async def __anext__(self) -> aiohttp.WSMessage:
        """The next answer, until there are no more."""
        if (message := await self._messages.get()) is None:
            raise StopAsyncIteration
        if isinstance(message, Exception):
            raise message
        if isinstance(message, aiohttp.WSMessage):
            return message
        return aiohttp.WSMessage(aiohttp.WSMsgType.TEXT, json.dumps(message), None)
