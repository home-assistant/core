"""Tests for the Honeywell Lyric select platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.lyric.const import DOMAIN
from homeassistant.components.select import ATTR_OPTIONS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MAC

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_lyric")
async def test_room_priority_with_non_thermostat_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test room priority remains available with non-thermostat devices."""
    with patch("homeassistant.components.lyric.PLATFORMS", [Platform.SELECT]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    entity_id = entity_registry.async_get_entity_id(
        Platform.SELECT, DOMAIN, f"{MAC}_room_priority"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "follow_me"
    assert state.attributes[ATTR_OPTIONS] == ["follow_me", "Living Room"]
