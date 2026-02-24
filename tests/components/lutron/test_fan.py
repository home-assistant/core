"""Test Lutron fan platform."""

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


async def test_fan_setup(
    hass: HomeAssistant,
    mock_lutron: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test fan setup."""
    mock_config_entry.add_to_hass(hass)

    fan = mock_lutron.areas[0].outputs[3]
    fan.level = 0
    fan.last_level.return_value = 0

    with patch("homeassistant.components.lutron.PLATFORMS", [Platform.FAN]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_fan_services(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test fan services."""
    mock_config_entry.add_to_hass(hass)

    fan = mock_lutron.areas[0].outputs[3]
    fan.level = 0
    fan.last_level.return_value = 0

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "fan.test_fan"

    # Turn on (defaults to medium - 67%)
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert fan.level == 67

    # Turn off
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert fan.level == 0

    # Set percentage
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PERCENTAGE: 33},
        blocking=True,
    )
    assert fan.level == 33


async def test_fan_update(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test fan state update."""
    mock_config_entry.add_to_hass(hass)

    fan = mock_lutron.areas[0].outputs[3]
    fan.level = 0
    fan.last_level.return_value = 0

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "fan.test_fan"
    assert hass.states.get(entity_id).state == STATE_OFF

    # Simulate update
    fan.last_level.return_value = 100
    callback = fan.subscribe.call_args[0][0]
    callback(fan, None, None, None)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON
    assert hass.states.get(entity_id).attributes[ATTR_PERCENTAGE] == 100
