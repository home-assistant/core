"""Tests for Broadlink climate."""

import pytest

from homeassistant.components.broadlink.climate import SensorMode
from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import get_device

testdata = [
    (
        SensorMode.INNER_SENSOR_CONTROL,
        1,
        0,
        1,
        22,
        23,
        30,
        HVACMode.HEAT,
        22,
        23,
        HVACAction.HEATING,
    ),
    (
        SensorMode.OUTER_SENSOR_CONTROL,
        1,
        1,
        0,
        22,
        23,
        30,
        HVACMode.AUTO,
        30,
        23,
        HVACAction.IDLE,
    ),
    (
        SensorMode.INNER_SENSOR_CONTROL,
        0,
        0,
        0,
        22,
        23,
        30,
        HVACMode.OFF,
        22,
        23,
        HVACAction.OFF,
    ),
]


@pytest.mark.parametrize(
    (
        "sensor",
        "power",
        "auto_mode",
        "active",
        "room_temp",
        "thermostat_temp",
        "external_temp",
        "expected_state",
        "expected_current_temperature",
        "expected_temperature",
        "expected_hvac_action",
    ),
    testdata,
)
async def test_climate(
    sensor,
    power,
    auto_mode,
    active,
    room_temp,
    thermostat_temp,
    external_temp,
    expected_state,
    expected_current_temperature,
    expected_temperature,
    expected_hvac_action,
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Broadlink climate."""

    device = get_device("Guest room")
    mock_setup = await device.setup_entry(hass)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    climates = [entry for entry in entries if entry.domain == Platform.CLIMATE]
    assert len(climates) == 1

    climate = climates[0]

    mock_setup.api.get_full_status.return_value = {
        "sensor": sensor.value,
        "power": power,
        "auto_mode": auto_mode,
        "active": active,
        "room_temp": room_temp,
        "thermostat_temp": thermostat_temp,
        "external_temp": external_temp,
    }

    await async_update_entity(hass, climate.entity_id)
    assert mock_setup.api.get_full_status.call_count == 2
    state = hass.states.get(climate.entity_id)
    assert state.state == expected_state
    assert state.attributes["current_temperature"] == expected_current_temperature
    assert state.attributes["temperature"] == expected_temperature
    assert state.attributes["hvac_action"] == expected_hvac_action


async def test_climate_set_temperature_turn_off_turn_on(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Broadlink climate."""

    device = get_device("Guest room")
    mock_setup = await device.setup_entry(hass)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    climates = [entry for entry in entries if entry.domain == Platform.CLIMATE]
    assert len(climates) == 1

    climate = climates[0]

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: climate.entity_id,
            ATTR_TEMPERATURE: "24",
        },
        blocking=True,
    )
    state = hass.states.get(climate.entity_id)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: climate.entity_id,
        },
        blocking=True,
    )
    state = hass.states.get(climate.entity_id)

    assert state.state == HVACMode.OFF

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: climate.entity_id,
        },
        blocking=True,
    )
    state = hass.states.get(climate.entity_id)

    assert state.state == HVACMode.HEAT
