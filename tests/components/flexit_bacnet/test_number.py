"""Tests for the Flexit Nordic (BACnet) number entities."""

from unittest.mock import AsyncMock

from flexit_bacnet import DecodingError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.number.const import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.flexit_bacnet import setup_with_selected_platforms

ENTITY_ID = "number.device_name_fireplace_supply_fan_setpoint"


async def test_numbers(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_flexit_bacnet: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test number states are correctly collected from library."""

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert (state := hass.states.get(entity_entry.entity_id))
        assert state == snapshot(name=f"{entity_entry.entity_id}-state")


async def test_numbers_implementation(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_flexit_bacnet: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the number can be changed."""

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])

    mock_flexit_bacnet.fan_setpoint_supply_air_fire = 60

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_VALUE: 60,
        },
        blocking=True,
    )

    mocked_method = getattr(mock_flexit_bacnet, "set_fan_setpoint_supply_air_fire")
    assert len(mocked_method.mock_calls) == 1
    assert hass.states.get(ENTITY_ID).state == "60"

    mock_flexit_bacnet.fan_setpoint_supply_air_fire = 10

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_VALUE: 10,
        },
        blocking=True,
    )

    mocked_method = getattr(mock_flexit_bacnet, "set_fan_setpoint_supply_air_fire")
    assert len(mocked_method.mock_calls) == 2
    assert hass.states.get(ENTITY_ID).state == "10"

    # Error recovery, when setting the value
    mock_flexit_bacnet.set_fan_setpoint_supply_air_fire.side_effect = DecodingError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_VALUE: 10,
            },
            blocking=True,
        )

    mocked_method = getattr(mock_flexit_bacnet, "set_fan_setpoint_supply_air_fire")
    assert len(mocked_method.mock_calls) == 3

    mock_flexit_bacnet.set_fan_setpoint_supply_air_fire.side_effect = None
    mock_flexit_bacnet.fan_setpoint_supply_air_fire = 30

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_VALUE: 30,
        },
        blocking=True,
    )

    assert hass.states.get(ENTITY_ID).state == "30"
