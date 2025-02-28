"""Tests for the niko_home_control integration."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

import pytest

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def find_update_callback(
    mock: AsyncMock, identifier: int
) -> Callable[[int], Awaitable[None]]:
    """Find the update callback for a specific identifier."""
    for call in mock.register_callback.call_args_list:
        if call[0][0] == identifier:
            return call[0][1]
    pytest.fail(f"Callback for identifier {identifier} not found")
