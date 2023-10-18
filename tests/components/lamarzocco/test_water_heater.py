"""Tests for the La Marzocco Water Heaters."""


from unittest.mock import MagicMock

import pytest

from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.components.water_heater import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_OPERATION_LIST,
    ATTR_OPERATION_MODE,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ELECTRIC,
    STATE_OFF,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_TEMPERATURE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_coffee_boiler(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the La Marzocco Coffee Boiler."""
    mock_lamarzocco.set_power.return_value = None
    mock_lamarzocco.set_coffee_temp.return_value = None

    state = hass.states.get("water_heater.GS01234_coffee_boiler")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "GS01234 Coffee Boiler"
    assert state.attributes.get(ATTR_ICON) == "mdi:coffee-maker"
    assert state.attributes.get(ATTR_TEMPERATURE) == 95.0
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 93.0
    assert state.attributes.get(ATTR_MIN_TEMP) == 85
    assert state.attributes.get(ATTR_MAX_TEMP) == 104
    assert state.attributes.get(ATTR_OPERATION_LIST) == [STATE_ELECTRIC, STATE_OFF]
    assert state.attributes.get(ATTR_OPERATION_MODE) == STATE_ELECTRIC
    assert state.state == STATE_ELECTRIC

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == "GS01234_coffee_boiler"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, "GS01234")}
    assert device.manufacturer == "La Marzocco"
    assert device.name == "GS01234"
    assert device.sw_version == "1.1"

    # on/off service calls
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: "water_heater.GS01234_coffee_boiler",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_power.mock_calls) == 1
    mock_lamarzocco.set_power.assert_called_once_with(enabled=False)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "water_heater.GS01234_coffee_boiler",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_power.mock_calls) == 2
    mock_lamarzocco.set_power.assert_called_with(enabled=True)

    # temp service calls
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "water_heater.GS01234_coffee_boiler",
            ATTR_TEMPERATURE: 96,
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_coffee_temp.mock_calls) == 1
    mock_lamarzocco.set_coffee_temp.assert_called_once_with(temperature=96)

    # operation service calls
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_OPERATION_MODE,
        {
            ATTR_ENTITY_ID: "water_heater.GS01234_coffee_boiler",
            ATTR_OPERATION_MODE: STATE_ELECTRIC,
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_power.mock_calls) == 3
    mock_lamarzocco.set_power.assert_called_with(enabled=True)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_OPERATION_MODE,
        {
            ATTR_ENTITY_ID: "water_heater.GS01234_coffee_boiler",
            ATTR_OPERATION_MODE: STATE_OFF,
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_power.mock_calls) == 4
    mock_lamarzocco.set_power.assert_called_with(enabled=False)


async def test_steam_boiler(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the La Marzocco Steam Boiler."""
    mock_lamarzocco.set_steam_boiler_enable.return_value = None
    mock_lamarzocco.set_steam_temp.return_value = None

    state = hass.states.get("water_heater.GS01234_steam_boiler")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "GS01234 Steam Boiler"
    assert state.attributes.get(ATTR_ICON) == "mdi:kettle-steam"
    assert state.attributes.get(ATTR_TEMPERATURE) == 128.0
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 113.0
    assert state.attributes.get(ATTR_MIN_TEMP) == 126
    assert state.attributes.get(ATTR_MAX_TEMP) == 131
    assert state.attributes.get(ATTR_OPERATION_LIST) == [STATE_ELECTRIC, STATE_OFF]
    assert state.attributes.get(ATTR_OPERATION_MODE) == STATE_ELECTRIC
    assert state.state == STATE_ELECTRIC

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == "GS01234_steam_boiler"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, "GS01234")}
    assert device.manufacturer == "La Marzocco"
    assert device.name == "GS01234"
    assert device.sw_version == "1.1"

    # on/off service calls
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: "water_heater.GS01234_steam_boiler",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_steam_boiler_enable.mock_calls) == 1
    mock_lamarzocco.set_steam_boiler_enable.assert_called_once_with(enable=False)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "water_heater.GS01234_steam_boiler",
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_steam_boiler_enable.mock_calls) == 2
    mock_lamarzocco.set_steam_boiler_enable.assert_called_with(enable=True)

    # temp service calls
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "water_heater.GS01234_steam_boiler",
            ATTR_TEMPERATURE: 131,
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_steam_temp.mock_calls) == 1
    mock_lamarzocco.set_steam_temp.assert_called_once_with(temperature=131)

    # operation service calls
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_OPERATION_MODE,
        {
            ATTR_ENTITY_ID: "water_heater.GS01234_steam_boiler",
            ATTR_OPERATION_MODE: STATE_ELECTRIC,
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_steam_boiler_enable.mock_calls) == 3
    mock_lamarzocco.set_steam_boiler_enable.assert_called_with(enable=True)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_OPERATION_MODE,
        {
            ATTR_ENTITY_ID: "water_heater.GS01234_steam_boiler",
            ATTR_OPERATION_MODE: STATE_OFF,
        },
        blocking=True,
    )

    assert len(mock_lamarzocco.set_steam_boiler_enable.mock_calls) == 4
    mock_lamarzocco.set_steam_boiler_enable.assert_called_with(enable=False)
