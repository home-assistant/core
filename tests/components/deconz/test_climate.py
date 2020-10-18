"""deCONZ climate platform tests."""

from copy import deepcopy

import pytest

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
)
from homeassistant.components.deconz.const import (
    CONF_ALLOW_CLIP_SENSOR,
    DOMAIN as DECONZ_DOMAIN,
)
from homeassistant.components.deconz.gateway import get_gateway_from_config_entry
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_OFF
from homeassistant.setup import async_setup_component

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration

from tests.async_mock import patch

SENSORS = {
    "1": {
        "id": "Thermostat id",
        "name": "Thermostat",
        "type": "ZHAThermostat",
        "state": {"on": True, "temperature": 2260, "valve": 30},
        "config": {
            "battery": 100,
            "heatsetpoint": 2200,
            "mode": "auto",
            "offset": 10,
            "reachable": True,
        },
        "uniqueid": "00:00:00:00:00:00:00:00-00",
    },
    "2": {
        "id": "CLIP thermostat id",
        "name": "CLIP thermostat",
        "type": "CLIPThermostat",
        "state": {"on": True, "temperature": 2260, "valve": 30},
        "config": {"reachable": True},
        "uniqueid": "00:00:00:00:00:00:00:02-00",
    },
}


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a gateway."""
    assert (
        await async_setup_component(
            hass, CLIMATE_DOMAIN, {"climate": {"platform": DECONZ_DOMAIN}}
        )
        is True
    )
    assert DECONZ_DOMAIN not in hass.data


async def test_no_sensors(hass):
    """Test that no sensors in deconz results in no climate entities."""
    await setup_deconz_integration(hass)
    assert len(hass.states.async_all()) == 0


async def test_climate_devices(hass):
    """Test successful creation of sensor entities."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = deepcopy(SENSORS)
    config_entry = await setup_deconz_integration(hass, get_state_response=data)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    assert len(hass.states.async_all()) == 2
    assert hass.states.get("climate.thermostat").state == HVAC_MODE_AUTO
    assert hass.states.get("sensor.thermostat") is None
    assert hass.states.get("sensor.thermostat_battery_level").state == "100"
    assert hass.states.get("climate.presence_sensor") is None
    assert hass.states.get("climate.clip_thermostat") is None

    # Event signals thermostat configured off

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "config": {"mode": "off"},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    assert hass.states.get("climate.thermostat").state == STATE_OFF

    # Event signals thermostat state on

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "config": {"mode": "other"},
        "state": {"on": True},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    assert hass.states.get("climate.thermostat").state == HVAC_MODE_HEAT

    # Event signals thermostat state off

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "state": {"on": False},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    assert hass.states.get("climate.thermostat").state == STATE_OFF

    # Verify service calls

    thermostat_device = gateway.api.sensors["1"]

    # Service set HVAC mode to auto

    with patch.object(thermostat_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.thermostat", ATTR_HVAC_MODE: HVAC_MODE_AUTO},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with(
            "put", "/sensors/1/config", json={"mode": "auto"}
        )

    # Service set HVAC mode to heat

    with patch.object(thermostat_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.thermostat", ATTR_HVAC_MODE: HVAC_MODE_HEAT},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with(
            "put", "/sensors/1/config", json={"mode": "heat"}
        )

    # Service set HVAC mode to off

    with patch.object(thermostat_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.thermostat", ATTR_HVAC_MODE: HVAC_MODE_OFF},
            blocking=True,
        )
        set_callback.assert_called_with(
            "put", "/sensors/1/config", json={"mode": "off"}
        )

    # Service set HVAC mode to unsupported value

    with patch.object(
        thermostat_device, "_request", return_value=True
    ) as set_callback, pytest.raises(ValueError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.thermostat", ATTR_HVAC_MODE: HVAC_MODE_COOL},
            blocking=True,
        )

    # Service set temperature to 20

    with patch.object(thermostat_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: "climate.thermostat", ATTR_TEMPERATURE: 20},
            blocking=True,
        )
        set_callback.assert_called_with(
            "put", "/sensors/1/config", json={"heatsetpoint": 2000.0}
        )

    # Service set temperature without providing temperature attribute

    with patch.object(
        thermostat_device, "_request", return_value=True
    ) as set_callback, pytest.raises(ValueError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.thermostat",
                ATTR_TARGET_TEMP_HIGH: 30,
                ATTR_TARGET_TEMP_LOW: 10,
            },
            blocking=True,
        )

    await hass.config_entries.async_unload(config_entry.entry_id)

    assert len(hass.states.async_all()) == 0


async def test_clip_climate_device(hass):
    """Test successful creation of sensor entities."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = deepcopy(SENSORS)
    config_entry = await setup_deconz_integration(
        hass,
        options={CONF_ALLOW_CLIP_SENSOR: True},
        get_state_response=data,
    )

    assert len(hass.states.async_all()) == 3
    assert hass.states.get("climate.thermostat").state == HVAC_MODE_AUTO
    assert hass.states.get("sensor.thermostat") is None
    assert hass.states.get("sensor.thermostat_battery_level").state == "100"
    assert hass.states.get("climate.clip_thermostat").state == HVAC_MODE_HEAT

    # Disallow clip sensors

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_ALLOW_CLIP_SENSOR: False}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2
    assert hass.states.get("climate.clip_thermostat") is None

    # Allow clip sensors

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_ALLOW_CLIP_SENSOR: True}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 3
    assert hass.states.get("climate.clip_thermostat").state == HVAC_MODE_HEAT


async def test_verify_state_update(hass):
    """Test that state update properly."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = deepcopy(SENSORS)
    config_entry = await setup_deconz_integration(hass, get_state_response=data)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    assert hass.states.get("climate.thermostat").state == HVAC_MODE_AUTO

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "state": {"on": False},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    assert hass.states.get("climate.thermostat").state == HVAC_MODE_AUTO
    assert gateway.api.sensors["1"].changed_keys == {"state", "r", "t", "on", "e", "id"}


async def test_add_new_climate_device(hass):
    """Test that adding a new climate device works."""
    config_entry = await setup_deconz_integration(hass)
    gateway = get_gateway_from_config_entry(hass, config_entry)
    assert len(hass.states.async_all()) == 0

    state_added_event = {
        "t": "event",
        "e": "added",
        "r": "sensors",
        "id": "1",
        "sensor": deepcopy(SENSORS["1"]),
    }
    gateway.api.event_handler(state_added_event)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2
    assert hass.states.get("climate.thermostat").state == HVAC_MODE_AUTO
    assert hass.states.get("sensor.thermostat_battery_level").state == "100"
