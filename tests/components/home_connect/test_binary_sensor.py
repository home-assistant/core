"""Tests for home_connect binary_sensor entities."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock, Mock

import pytest

from homeassistant.components.home_connect.const import ATTR_VALUE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from tests.common import MockConfigEntry

BSH_REMOTE_CONTROL_ACTIVATION_STATE = "BSH.Common.Status.RemoteControlActive"


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.BINARY_SENSOR]


@pytest.mark.usefixtures("bypass_throttle")
async def test_binary_sensors(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
    appliance: Mock,
) -> None:
    """Test binary sensor entities."""
    get_appliances.return_value = [appliance]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (False, "off"),
        (True, "on"),
        ("", "unavailable"),
    ],
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_binary_sensors_door_states(
    expected: str,
    state: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
    appliance: Mock,
) -> None:
    """Tests for Appliance door states."""
    entity_id = "binary_sensor.washer_remote_control"
    get_appliances.return_value = [appliance]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    appliance.status.update({BSH_REMOTE_CONTROL_ACTIVATION_STATE: {}})
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED
    appliance.status.update({BSH_REMOTE_CONTROL_ACTIVATION_STATE: {ATTR_VALUE: state}})
    await async_update_entity(hass, entity_id)
    await hass.async_block_till_done()
    assert hass.states.is_state(entity_id, expected)
