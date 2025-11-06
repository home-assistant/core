"""Tests for (un-)subscribing device-updated callbacks on entity adding/removal."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def platform() -> Platform:
    """Use the light platform for this test."""
    return Platform.LIGHT


@pytest.mark.usefixtures("setup_integration")
async def test_entity_callbacks(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_light: AsyncMock,
) -> None:
    """Ensure the entity unregisters its device-updated callback when unloaded."""
    # Entity is created by setup_integration; callback should be registered
    test_entity_id = f"light.{mock_light.name.lower().replace(' ', '_')}"
    state = hass.states.get(test_entity_id)
    assert state is not None

    # Callback is registered exactly once with a callable
    assert mock_light.register_device_updated_cb.call_count == 1
    cb = mock_light.register_device_updated_cb.call_args[0][0]
    assert callable(cb)

    # Unload the config entry to trigger async_will_remove_from_hass
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Callback must be unregistered with the same callable
    assert mock_light.unregister_device_updated_cb.call_count == 1
    assert mock_light.unregister_device_updated_cb.call_args[0][0] is cb
