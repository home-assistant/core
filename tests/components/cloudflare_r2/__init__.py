"""Tests for the Cloudflare R2 integration."""

import asyncio
from unittest.mock import MagicMock

from aiobotocore.response import StreamingBody
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the Cloudflare R2 integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


def mock_streaming_body(data: bytes) -> StreamingBody:
    """Return a get_object body which streams data from a mocked response."""
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    reader.feed_eof()
    return StreamingBody(MagicMock(content=reader), str(len(data)))
