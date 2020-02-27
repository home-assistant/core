"""deCONZ climate platform tests."""
from copy import deepcopy

from asynctest import patch

from homeassistant.components import deconz
import homeassistant.components.climate as climate
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
        "id": "Presence sensor id",
        "name": "Presence sensor",
        "type": "ZHAPresence",
        "state": {"presence": False},
        "config": {"reachable": True},
        "uniqueid": "00:00:00:00:00:00:00:01-00",
    },
    "3": {
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
            hass, climate.DOMAIN, {"climate": {"platform": deconz.DOMAIN}}
        )
        is True
    )
    assert deconz.DOMAIN not in hass.data


async def test_no_sensors(hass):
    """Test that no sensors in deconz results in no climate entities."""
    gateway = await setup_deconz_integration(hass)
    assert len(gateway.deconz_ids) == 0
    assert len(hass.states.async_all()) == 0


async def test_climate_devices(hass):
    """Test successful creation of sensor entities."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = deepcopy(SENSORS)
    gateway = await setup_deconz_integration(hass, get_state_response=data)
    assert "climate.thermostat" in gateway.deconz_ids
    assert "sensor.thermostat" not in gateway.deconz_ids
    assert "sensor.thermostat_battery_level" in gateway.deconz_ids
    assert "climate.presence_sensor" not in gateway.deconz_ids
    assert "climate.clip_thermostat" not in gateway.deconz_ids
    assert len(hass.states.async_all()) == 3

    thermostat = hass.states.get("climate.thermostat")
    assert thermostat.state == "auto"

    thermostat = hass.states.get("sensor.thermostat")
    assert thermostat is None

    thermostat_battery_level = hass.states.get("sensor.thermostat_battery_level")
    assert thermostat_battery_level.state == "100"

    presence_sensor = hass.states.get("climate.presence_sensor")
    assert presence_sensor is None

    clip_thermostat = hass.states.get("climate.clip_thermostat")
    assert clip_thermostat is None

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "config": {"mode": "off"},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    thermostat = hass.states.get("climate.thermostat")
    assert thermostat.state == "off"

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

    thermostat = hass.states.get("climate.thermostat")
    assert thermostat.state == "heat"

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "state": {"on": False},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    thermostat = hass.states.get("climate.thermostat")
    assert thermostat.state == "off"

    # Verify service calls

    thermostat_device = gateway.api.sensors["1"]

    with patch.object(thermostat_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            climate.DOMAIN,
            climate.SERVICE_SET_HVAC_MODE,
            {"entity_id": "climate.thermostat", "hvac_mode": "auto"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with(
            "put", "/sensors/1/config", json={"mode": "auto"}
        )

    with patch.object(thermostat_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            climate.DOMAIN,
            climate.SERVICE_SET_HVAC_MODE,
            {"entity_id": "climate.thermostat", "hvac_mode": "heat"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with(
            "put", "/sensors/1/config", json={"mode": "heat"}
        )

    with patch.object(thermostat_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            climate.DOMAIN,
            climate.SERVICE_SET_HVAC_MODE,
            {"entity_id": "climate.thermostat", "hvac_mode": "off"},
            blocking=True,
        )
        set_callback.assert_called_with(
            "put", "/sensors/1/config", json={"mode": "off"}
        )

    with patch.object(thermostat_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            climate.DOMAIN,
            climate.SERVICE_SET_TEMPERATURE,
            {"entity_id": "climate.thermostat", "temperature": 20},
            blocking=True,
        )
        set_callback.assert_called_with(
            "put", "/sensors/1/config", json={"heatsetpoint": 2000.0}
        )

    await gateway.async_reset()

    assert len(hass.states.async_all()) == 0


async def test_clip_climate_device(hass):
    """Test successful creation of sensor entities."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = deepcopy(SENSORS)
    gateway = await setup_deconz_integration(
        hass,
        options={deconz.gateway.CONF_ALLOW_CLIP_SENSOR: True},
        get_state_response=data,
    )
    assert "climate.thermostat" in gateway.deconz_ids
    assert "sensor.thermostat" not in gateway.deconz_ids
    assert "sensor.thermostat_battery_level" in gateway.deconz_ids
    assert "climate.presence_sensor" not in gateway.deconz_ids
    assert "climate.clip_thermostat" in gateway.deconz_ids
    assert len(hass.states.async_all()) == 4

    thermostat = hass.states.get("climate.thermostat")
    assert thermostat.state == "auto"

    thermostat = hass.states.get("sensor.thermostat")
    assert thermostat is None

    thermostat_battery_level = hass.states.get("sensor.thermostat_battery_level")
    assert thermostat_battery_level.state == "100"

    presence_sensor = hass.states.get("climate.presence_sensor")
    assert presence_sensor is None

    clip_thermostat = hass.states.get("climate.clip_thermostat")
    assert clip_thermostat.state == "heat"

    hass.config_entries.async_update_entry(
        gateway.config_entry, options={deconz.gateway.CONF_ALLOW_CLIP_SENSOR: False}
    )
    await hass.async_block_till_done()

    assert "climate.thermostat" in gateway.deconz_ids
    assert "sensor.thermostat" not in gateway.deconz_ids
    assert "sensor.thermostat_battery_level" in gateway.deconz_ids
    assert "climate.presence_sensor" not in gateway.deconz_ids
    assert "climate.clip_thermostat" not in gateway.deconz_ids
    assert len(hass.states.async_all()) == 3

    hass.config_entries.async_update_entry(
        gateway.config_entry, options={deconz.gateway.CONF_ALLOW_CLIP_SENSOR: True}
    )
    await hass.async_block_till_done()

    assert "climate.thermostat" in gateway.deconz_ids
    assert "sensor.thermostat" not in gateway.deconz_ids
    assert "sensor.thermostat_battery_level" in gateway.deconz_ids
    assert "climate.presence_sensor" not in gateway.deconz_ids
    assert "climate.clip_thermostat" in gateway.deconz_ids
    assert len(hass.states.async_all()) == 4


async def test_verify_state_update(hass):
    """Test that state update properly."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = deepcopy(SENSORS)
    gateway = await setup_deconz_integration(hass, get_state_response=data)
    assert "climate.thermostat" in gateway.deconz_ids

    thermostat = hass.states.get("climate.thermostat")
    assert thermostat.state == "auto"

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "state": {"on": False},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    thermostat = hass.states.get("climate.thermostat")
    assert thermostat.state == "auto"
    assert gateway.api.sensors["1"].changed_keys == {"state", "r", "t", "on", "e", "id"}


async def test_add_new_climate_device(hass):
    """Test that adding a new climate device works."""
    gateway = await setup_deconz_integration(hass)
    assert len(gateway.deconz_ids) == 0

    state_added_event = {
        "t": "event",
        "e": "added",
        "r": "sensors",
        "id": "1",
        "sensor": deepcopy(SENSORS["1"]),
    }
    gateway.api.event_handler(state_added_event)
    await hass.async_block_till_done()

    assert "climate.thermostat" in gateway.deconz_ids

    thermostat = hass.states.get("climate.thermostat")
    assert thermostat.state == "auto"
