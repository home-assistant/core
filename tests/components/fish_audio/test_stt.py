"""Tests for the Fish Audio STT entity."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.components.fish_audio.const import CONF_API_KEY, DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _pcm_bytes() -> bytes:
    # few non-zero 16-bit PCM little-endian samples @ 16kHz
    # 0x0001, 0x0002, 0x0003, 0x0004
    return b"\x01\x00\x02\x00\x03\x00\x04\x00"


async def _astream(chunks: list[bytes]):
    for c in chunks:
        yield c


@pytest.mark.asyncio
async def test_stt_happy_path_calls_asr_and_returns_text(
    hass: HomeAssistant,
    mock_async_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-empty PCM -> wrapped WAV -> session.asr called -> SUCCESS with text."""
    # Config entry with runtime session
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key123"},
        options={},  # STT options not required
        title="Fish Audio",
    )
    session = mock_async_client.return_value
    entry.runtime_data = session

    captured = {}

    def fake_asr(request):
        # Capture the request object the entity builds
        captured["request"]()
