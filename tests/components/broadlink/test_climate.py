"""Tests for Broadlink climate."""

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


async def test_climate_inner_heat_heating(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Broadlink climate.

    The test initialized with:
    - SensorMode.INNER_SENSOR_CONTROL
    - HVACMode.HEAT
    - HVACAction.HEATING
    """
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
        "sensor": SensorMode.INNER_SENSOR_CONTROL,
        "power": 1,
        "auto_mode": 0,
        "active": 1,
        "room_temp": 22,
        "thermostat_temp": 23,
        "external_temp": 30,
    }

    await async_update_entity(hass, climate.entity_id)
    assert mock_setup.api.get_full_status.call_count == 2
    state = hass.states.get(climate.entity_id)
    assert state.state == HVACMode.HEAT
    assert state.attributes["current_temperature"] == 22
    assert state.attributes["temperature"] == 23
    assert state.attributes["hvac_action"] == HVACAction.HEATING

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
    assert state.state == HVACMode.HEAT
    assert state.attributes["current_temperature"] == 22
    assert state.attributes["temperature"] == 24
    assert state.attributes["hvac_action"] == HVACAction.HEATING

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
    assert state.attributes["current_temperature"] == 22
    assert state.attributes["temperature"] == 24
    assert state.attributes["hvac_action"] == HVACAction.HEATING

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
    assert state.attributes["current_temperature"] == 22
    assert state.attributes["temperature"] == 24
    assert state.attributes["hvac_action"] == HVACAction.HEATING


async def test_climate_outer_auto_idle(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Broadlink climate.

    The test initialized with:
    - SensorMode.OUTER_SENSOR_CONTROL
    - HVACMode.AUTO
    - HVACAction.IDLE
    """
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
        "sensor": SensorMode.OUTER_SENSOR_CONTROL,
        "power": 1,
        "auto_mode": 1,
        "active": 0,
        "room_temp": 22,
        "thermostat_temp": 23,
        "external_temp": 30,
    }

    await async_update_entity(hass, climate.entity_id)
    assert mock_setup.api.get_full_status.call_count == 2
    state = hass.states.get(climate.entity_id)
    assert state.state == HVACMode.AUTO
    assert state.attributes["current_temperature"] == 30
    assert state.attributes["temperature"] == 23
    assert state.attributes["hvac_action"] == HVACAction.IDLE


async def test_climate_inner_off_off(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Broadlink climate.

    The test initialized with:
    - SensorMode.INNER_SENSOR_CONTROL
    - HVACMode.OFF
    - HVACAction.OFF
    """
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
        "sensor": SensorMode.INNER_SENSOR_CONTROL,
        "power": 0,
        "auto_mode": 0,
        "active": 0,
        "room_temp": 22,
        "thermostat_temp": 23,
        "external_temp": 30,
    }

    await async_update_entity(hass, climate.entity_id)
    assert mock_setup.api.get_full_status.call_count == 2
    state = hass.states.get(climate.entity_id)
    assert state.state == HVACMode.OFF
    assert state.attributes["current_temperature"] == 22
    assert state.attributes["temperature"] == 23
    assert state.attributes["hvac_action"] == HVACAction.OFF
