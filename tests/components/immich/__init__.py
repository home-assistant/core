"""Tests for the Immich integration."""

from homeassistant.core import HomeAssistant
from homeassistant.util.aiohttp import MockStreamReader

from tests.common import MockConfigEntry


class MockStreamReaderChunked(MockStreamReader):
    """Mock a stream reader with simulated chunked data."""

    async def readchunk(self) -> tuple[bytes, bool]:
        """Read bytes."""
        return (self._content.read(), False)


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
