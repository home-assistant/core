"""Tests for the lg_soundbar component."""

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def find_update_callback(
    mock: MagicMock,
) -> Callable[[dict[str, Any]], None]:
    """Return the callback registered with the temescal device."""
    return mock.call_args.kwargs["callback"]
