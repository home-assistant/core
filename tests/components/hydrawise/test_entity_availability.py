"""Test entity availability."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from unittest.mock import AsyncMock

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from pydrawise.schema import Controller

from homeassistant.components.hydrawise.const import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed

_SPECIAL_ENTITIES = {"binary_sensor.home_controller_connectivity": STATE_OFF}


async def test_controller_offline(
    hass: HomeAssistant,
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
    entity_registry: er.EntityRegistry,
    controller: Controller,
) -> None:
    """Test availability for sensors when controller is offline."""
    controller.online = False
    config_entry = await mock_add_config_entry()
    _test_availability(hass, config_entry, entity_registry)


async def test_api_offline(
    hass: HomeAssistant,
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
    entity_registry: er.EntityRegistry,
    mock_pydrawise: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test availability of sensors when API call fails."""
    config_entry = await mock_add_config_entry()
    mock_pydrawise.get_user.reset_mock(return_value=True)
    mock_pydrawise.get_user.side_effect = ClientError
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    _test_availability(hass, config_entry, entity_registry)


def _test_availability(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries
    for entity_entry in entity_entries:
        state = hass.states.get(entity_entry.entity_id)
        assert state, f"State not found for {entity_entry.entity_id}"
        assert state.state == _SPECIAL_ENTITIES.get(
            entity_entry.entity_id, STATE_UNAVAILABLE
        )
