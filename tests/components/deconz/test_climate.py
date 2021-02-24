"""deCONZ climate platform tests."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.climate.const import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    FAN_ON,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_COMFORT,
)
from homeassistant.components.deconz.climate import (
    DECONZ_FAN_SMART,
    DECONZ_PRESET_MANUAL,
)
from homeassistant.components.deconz.const import (
    CONF_ALLOW_CLIP_SENSOR,
    DOMAIN as DECONZ_DOMAIN,
)
from homeassistant.components.deconz.gateway import get_gateway_from_config_entry
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_OFF
from homeassistant.setup import async_setup_component

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration

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


async def test_simple_climate_device(hass):
    """Test successful creation of climate entities.

    This is a simple water heater that only supports setting temperature and on and off.
    """
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = {
        "0": {
            "config": {
                "battery": 59,
                "displayflipped": None,
                "heatsetpoint": 2100,
                "locked": None,
                "mountingmode": None,
                "offset": 0,
                "on": True,
                "reachable": True,
            },
            "ep": 1,
            "etag": "6130553ac247174809bae47144ee23f8",
            "lastseen": "2020-11-29T19:31Z",
            "manufacturername": "Danfoss",
            "modelid": "eTRV0100",
            "name": "thermostat",
            "state": {
                "errorcode": None,
                "lastupdated": "2020-11-29T19:28:40.665",
                "mountingmodeactive": False,
                "on": True,
                "temperature": 2102,
                "valve": 24,
                "windowopen": "Closed",
            },
            "swversion": "01.02.0008 01.02",
            "type": "ZHAThermostat",
            "uniqueid": "14:b4:57:ff:fe:d5:4e:77-01-0201",
        }
    }
    config_entry = await setup_deconz_integration(hass, get_state_response=data)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    assert len(hass.states.async_all()) == 2
    climate_thermostat = hass.states.get("climate.thermostat")
    assert climate_thermostat.state == HVAC_MODE_HEAT
    assert climate_thermostat.attributes["hvac_modes"] == [
        HVAC_MODE_HEAT,
        HVAC_MODE_OFF,
    ]
    assert climate_thermostat.attributes["current_temperature"] == 21.0
    assert climate_thermostat.attributes["temperature"] == 21.0
    assert hass.states.get("sensor.thermostat_battery_level").state == "59"

    # Event signals thermostat configured off

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "state": {"on": False},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    assert hass.states.get("climate.thermostat").state == STATE_OFF

    # Event signals thermostat state on

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "state": {"on": True},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    assert hass.states.get("climate.thermostat").state == HVAC_MODE_HEAT

    # Verify service calls

    thermostat_device = gateway.api.sensors["0"]

    # Service turn on thermostat

    with patch.object(thermostat_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.thermostat", ATTR_HVAC_MODE: HVAC_MODE_HEAT},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/sensors/0/config", json={"on": True})

    # Service turn on thermostat

    with patch.object(thermostat_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.thermostat", ATTR_HVAC_MODE: HVAC_MODE_OFF},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/sensors/0/config", json={"on": False})

    # Service set HVAC mode to unsupported value

    with patch.object(
        thermostat_device, "_request", return_value=True
    ) as set_callback, pytest.raises(ValueError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.thermostat", ATTR_HVAC_MODE: HVAC_MODE_AUTO},
            blocking=True,
        )


async def test_climate_device_without_cooling_support(hass):
    """Test successful creation of sensor entities."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = deepcopy(SENSORS)
    config_entry = await setup_deconz_integration(hass, get_state_response=data)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    assert len(hass.states.async_all()) == 2
    climate_thermostat = hass.states.get("climate.thermostat")
    assert climate_thermostat.state == HVAC_MODE_AUTO
    assert climate_thermostat.attributes["hvac_modes"] == [
        HVAC_MODE_AUTO,
        HVAC_MODE_HEAT,
        HVAC_MODE_OFF,
    ]
    assert climate_thermostat.attributes["current_temperature"] == 22.6
    assert climate_thermostat.attributes["temperature"] == 22.0
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


async def test_climate_device_with_cooling_support(hass):
    """Test successful creation of sensor entities."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = {
        "0": {
            "config": {
                "battery": 25,
                "coolsetpoint": None,
                "fanmode": None,
                "heatsetpoint": 2222,
                "mode": "heat",
                "offset": 0,
                "on": True,
                "reachable": True,
            },
            "ep": 1,
            "etag": "074549903686a77a12ef0f06c499b1ef",
            "lastseen": "2020-11-27T13:45Z",
            "manufacturername": "Zen Within",
            "modelid": "Zen-01",
            "name": "Zen-01",
            "state": {
                "lastupdated": "2020-11-27T13:42:40.863",
                "on": False,
                "temperature": 2320,
            },
            "type": "ZHAThermostat",
            "uniqueid": "00:24:46:00:00:11:6f:56-01-0201",
        }
    }
    config_entry = await setup_deconz_integration(hass, get_state_response=data)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    assert len(hass.states.async_all()) == 2
    climate_thermostat = hass.states.get("climate.zen_01")
    assert climate_thermostat.state == HVAC_MODE_HEAT
    assert climate_thermostat.attributes["hvac_modes"] == [
        HVAC_MODE_AUTO,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT,
        HVAC_MODE_OFF,
    ]
    assert climate_thermostat.attributes["current_temperature"] == 23.2
    assert climate_thermostat.attributes["temperature"] == 22.2
    assert hass.states.get("sensor.zen_01_battery_level").state == "25"

    # Event signals thermostat state cool

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "config": {"mode": "cool"},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    assert hass.states.get("climate.zen_01").state == HVAC_MODE_COOL

    # Verify service calls

    thermostat_device = gateway.api.sensors["0"]

    # Service set temperature to 20

    with patch.object(thermostat_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: "climate.zen_01", ATTR_TEMPERATURE: 20},
            blocking=True,
        )
        set_callback.assert_called_with(
            "put", "/sensors/0/config", json={"coolsetpoint": 2000.0}
        )


async def test_climate_device_with_fan_support(hass):
    """Test successful creation of sensor entities."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = {
        "0": {
            "config": {
                "battery": 25,
                "coolsetpoint": None,
                "fanmode": "auto",
                "heatsetpoint": 2222,
                "mode": "heat",
                "offset": 0,
                "on": True,
                "reachable": True,
            },
            "ep": 1,
            "etag": "074549903686a77a12ef0f06c499b1ef",
            "lastseen": "2020-11-27T13:45Z",
            "manufacturername": "Zen Within",
            "modelid": "Zen-01",
            "name": "Zen-01",
            "state": {
                "lastupdated": "2020-11-27T13:42:40.863",
                "on": False,
                "temperature": 2320,
            },
            "type": "ZHAThermostat",
            "uniqueid": "00:24:46:00:00:11:6f:56-01-0201",
        }
    }
    config_entry = await setup_deconz_integration(hass, get_state_response=data)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    assert len(hass.states.async_all()) == 2
    climate_thermostat = hass.states.get("climate.zen_01")
    assert climate_thermostat.state == HVAC_MODE_HEAT
    assert climate_thermostat.attributes["fan_mode"] == FAN_AUTO
    assert climate_thermostat.attributes["fan_modes"] == [
        DECONZ_FAN_SMART,
        FAN_AUTO,
        FAN_HIGH,
        FAN_MEDIUM,
        FAN_LOW,
        FAN_ON,
        FAN_OFF,
    ]

    # Event signals fan mode defaults to off

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "config": {"fanmode": "unsupported"},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    assert hass.states.get("climate.zen_01").attributes["fan_mode"] == FAN_OFF

    # Event signals unsupported fan mode

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "config": {"fanmode": "unsupported"},
        "state": {"on": True},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    assert hass.states.get("climate.zen_01").attributes["fan_mode"] == FAN_ON

    # Event signals unsupported fan mode

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "config": {"fanmode": "unsupported"},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    assert hass.states.get("climate.zen_01").attributes["fan_mode"] == FAN_ON

    # Verify service calls

    thermostat_device = gateway.api.sensors["0"]

    # Service set fan mode to off

    with patch.object(thermostat_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: "climate.zen_01", ATTR_FAN_MODE: FAN_OFF},
            blocking=True,
        )
        set_callback.assert_called_with(
            "put", "/sensors/0/config", json={"fanmode": "off"}
        )

    # Service set fan mode to custom deCONZ mode smart

    with patch.object(thermostat_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: "climate.zen_01", ATTR_FAN_MODE: DECONZ_FAN_SMART},
            blocking=True,
        )
        set_callback.assert_called_with(
            "put", "/sensors/0/config", json={"fanmode": "smart"}
        )

    # Service set fan mode to unsupported value

    with patch.object(
        thermostat_device, "_request", return_value=True
    ) as set_callback, pytest.raises(ValueError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: "climate.zen_01", ATTR_FAN_MODE: "unsupported"},
            blocking=True,
        )


async def test_climate_device_with_preset(hass):
    """Test successful creation of sensor entities."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = {
        "0": {
            "config": {
                "battery": 25,
                "coolsetpoint": None,
                "fanmode": None,
                "heatsetpoint": 2222,
                "mode": "heat",
                "preset": "auto",
                "offset": 0,
                "on": True,
                "reachable": True,
            },
            "ep": 1,
            "etag": "074549903686a77a12ef0f06c499b1ef",
            "lastseen": "2020-11-27T13:45Z",
            "manufacturername": "Zen Within",
            "modelid": "Zen-01",
            "name": "Zen-01",
            "state": {
                "lastupdated": "2020-11-27T13:42:40.863",
                "on": False,
                "temperature": 2320,
            },
            "type": "ZHAThermostat",
            "uniqueid": "00:24:46:00:00:11:6f:56-01-0201",
        }
    }
    config_entry = await setup_deconz_integration(hass, get_state_response=data)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    assert len(hass.states.async_all()) == 2

    climate_zen_01 = hass.states.get("climate.zen_01")
    assert climate_zen_01.state == HVAC_MODE_HEAT
    assert climate_zen_01.attributes["current_temperature"] == 23.2
    assert climate_zen_01.attributes["temperature"] == 22.2
    assert climate_zen_01.attributes["preset_mode"] == "auto"
    assert climate_zen_01.attributes["preset_modes"] == [
        "auto",
        "boost",
        "comfort",
        "complex",
        "eco",
        "holiday",
        "manual",
    ]

    # Event signals deCONZ preset

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "config": {"preset": "manual"},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    assert (
        hass.states.get("climate.zen_01").attributes["preset_mode"]
        == DECONZ_PRESET_MANUAL
    )

    # Event signals unknown preset

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "config": {"preset": "unsupported"},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    assert hass.states.get("climate.zen_01").attributes["preset_mode"] is None

    # Verify service calls

    thermostat_device = gateway.api.sensors["0"]

    # Service set preset to HASS preset

    with patch.object(thermostat_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: "climate.zen_01", ATTR_PRESET_MODE: PRESET_COMFORT},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with(
            "put", "/sensors/0/config", json={"preset": "comfort"}
        )

    # Service set preset to custom deCONZ preset

    with patch.object(thermostat_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: "climate.zen_01", ATTR_PRESET_MODE: DECONZ_PRESET_MANUAL},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with(
            "put", "/sensors/0/config", json={"preset": "manual"}
        )

    # Service set preset to unsupported value

    with patch.object(
        thermostat_device, "_request", return_value=True
    ) as set_callback, pytest.raises(ValueError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: "climate.zen_01", ATTR_PRESET_MODE: "unsupported"},
            blocking=True,
        )


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
