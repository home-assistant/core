"""Tests for the Miele integration."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def get_callback(
    mock: AsyncMock, the_callback: str
) -> Callable[[int], Awaitable[None]]:
    """Get registered callbacks for api push."""
    return mock.listen_events.call_args_list[0].kwargs.get(the_callback)
