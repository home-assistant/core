"""Test ESPHome water heaters."""

from unittest.mock import call

from aioesphomeapi import APIClient, WaterHeaterInfo, WaterHeaterMode, WaterHeaterState

from homeassistant.components.water_heater import (
    ATTR_OPERATION_LIST,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant

from .conftest import MockGenericDeviceEntryType


async def test_water_heater_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic water heater entity."""
    entity_info = [
        WaterHeaterInfo(
            object_id="my_boiler",
            key=1,
            name="My Boiler",
            min_temperature=10.0,
            max_temperature=85.0,
            supported_modes=[
                WaterHeaterMode.ECO,
                WaterHeaterMode.GAS,
            ],
        )
    ]
    states = [
        WaterHeaterState(
            key=1,
            mode=WaterHeaterMode.ECO,
            current_temperature=45.0,
            target_temperature=50.0,
        )
    ]

    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )

    state = hass.states.get("water_heater.test_my_boiler")
    assert state is not None
    assert state.state == "eco"
    assert state.attributes["current_temperature"] == 45.0
    assert state.attributes["temperature"] == 50.0
    assert state.attributes["min_temp"] == 10.0
    assert state.attributes["max_temp"] == 85.0
    assert state.attributes["operation_list"] == ["eco", "gas"]


async def test_water_heater_entity_no_modes(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a water heater entity without operation modes."""
    entity_info = [
        WaterHeaterInfo(
            object_id="my_boiler",
            key=1,
            name="My Boiler",
            min_temperature=10.0,
            max_temperature=85.0,
        )
    ]
    states = [
        WaterHeaterState(
            key=1,
            current_temperature=45.0,
            target_temperature=50.0,
        )
    ]

    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )

    state = hass.states.get("water_heater.test_my_boiler")
    assert state is not None
    assert state.attributes["min_temp"] == 10.0
    assert state.attributes["max_temp"] == 85.0
    assert state.attributes.get(ATTR_OPERATION_LIST) is None


async def test_water_heater_set_temperature(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test setting the target temperature."""
    entity_info = [
        WaterHeaterInfo(
            object_id="my_boiler",
            key=1,
            name="My Boiler",
            min_temperature=10.0,
            max_temperature=85.0,
        )
    ]
    states = [
        WaterHeaterState(
            key=1,
            mode=WaterHeaterMode.ECO,
            target_temperature=45.0,
        )
    ]

    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "water_heater.test_my_boiler",
            ATTR_TEMPERATURE: 55,
        },
        blocking=True,
    )

    mock_client.water_heater_command.assert_has_calls(
        [call(key=1, target_temperature=55.0, device_id=0)]
    )


async def test_water_heater_set_operation_mode(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test setting the operation mode."""
    entity_info = [
        WaterHeaterInfo(
            object_id="my_boiler",
            key=1,
            name="My Boiler",
            supported_modes=[
                WaterHeaterMode.ECO,
                WaterHeaterMode.GAS,
            ],
        )
    ]
    states = [
        WaterHeaterState(
            key=1,
            mode=WaterHeaterMode.ECO,
        )
    ]

    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_OPERATION_MODE,
        {
            ATTR_ENTITY_ID: "water_heater.test_my_boiler",
            "operation_mode": "gas",
        },
        blocking=True,
    )

    mock_client.water_heater_command.assert_has_calls(
        [call(key=1, mode=WaterHeaterMode.GAS, device_id=0)]
    )
