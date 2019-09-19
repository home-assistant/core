"""deCONZ binary sensor platform tests."""
from copy import deepcopy

from asynctest import patch

from homeassistant import config_entries
from homeassistant.components import deconz
from homeassistant.setup import async_setup_component

import homeassistant.components.binary_sensor as binary_sensor


SENSORS = {
    "1": {
        "id": "Presence sensor id",
        "name": "Presence sensor",
        "type": "ZHAPresence",
        "state": {"dark": False, "presence": False},
        "config": {"on": True, "reachable": True, "temperature": 10},
        "uniqueid": "00:00:00:00:00:00:00:00-00",
    },
    "2": {
        "id": "Temperature sensor id",
        "name": "Temperature sensor",
        "type": "ZHATemperature",
        "state": {"temperature": False},
        "config": {},
        "uniqueid": "00:00:00:00:00:00:00:01-00",
    },
    "3": {
        "id": "CLIP presence sensor id",
        "name": "CLIP presence sensor",
        "type": "CLIPPresence",
        "state": {},
        "config": {},
        "uniqueid": "00:00:00:00:00:00:00:02-00",
    },
    "4": {
        "id": "Vibration sensor id",
        "name": "Vibration sensor",
        "type": "ZHAVibration",
        "state": {
            "orientation": [1, 2, 3],
            "tiltangle": 36,
            "vibration": True,
            "vibrationstrength": 10,
        },
        "config": {"on": True, "reachable": True, "temperature": 10},
        "uniqueid": "00:00:00:00:00:00:00:03-00",
    },
}

BRIDGEID = "0123456789"

ENTRY_CONFIG = {
    deconz.config_flow.CONF_API_KEY: "ABCDEF",
    deconz.config_flow.CONF_BRIDGEID: BRIDGEID,
    deconz.config_flow.CONF_HOST: "1.2.3.4",
    deconz.config_flow.CONF_PORT: 80,
}

DECONZ_CONFIG = {
    "bridgeid": BRIDGEID,
    "mac": "00:11:22:33:44:55",
    "name": "deCONZ mock gateway",
    "sw_version": "2.05.69",
    "websocketport": 1234,
}

DECONZ_WEB_REQUEST = {"config": DECONZ_CONFIG}


async def setup_deconz_integration(hass, config, options, get_state_response):
    """Create the deCONZ gateway."""
    config_entry = config_entries.ConfigEntry(
        version=1,
        domain=deconz.DOMAIN,
        title="Mock Title",
        data=config,
        source="test",
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
        system_options={},
        options=options,
        entry_id="1",
    )

    with patch(
        "pydeconz.DeconzSession.async_get_state", return_value=get_state_response
    ), patch("pydeconz.DeconzSession.start", return_value=True):
        await deconz.async_setup_entry(hass, config_entry)
    await hass.async_block_till_done()

    hass.config_entries._entries.append(config_entry)

    return hass.data[deconz.DOMAIN][config[deconz.CONF_BRIDGEID]]


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a gateway."""
    assert (
        await async_setup_component(
            hass, binary_sensor.DOMAIN, {"binary_sensor": {"platform": deconz.DOMAIN}}
        )
        is True
    )
    assert deconz.DOMAIN not in hass.data


async def test_no_binary_sensors(hass):
    """Test that no sensors in deconz results in no sensor entities."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    gateway = await setup_deconz_integration(
        hass, ENTRY_CONFIG, options={}, get_state_response=data
    )
    assert len(gateway.deconz_ids) == 0
    assert len(hass.states.async_all()) == 0


async def test_binary_sensors(hass):
    """Test successful creation of binary sensor entities."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = deepcopy(SENSORS)
    gateway = await setup_deconz_integration(
        hass, ENTRY_CONFIG, options={}, get_state_response=data
    )
    assert "binary_sensor.presence_sensor" in gateway.deconz_ids
    assert "binary_sensor.temperature_sensor" not in gateway.deconz_ids
    assert "binary_sensor.clip_presence_sensor" not in gateway.deconz_ids
    assert "binary_sensor.vibration_sensor" in gateway.deconz_ids
    assert len(hass.states.async_all()) == 3

    presence_sensor = hass.states.get("binary_sensor.presence_sensor")
    assert presence_sensor.state == "off"

    temperature_sensor = hass.states.get("binary_sensor.temperature_sensor")
    assert temperature_sensor is None

    clip_presence_sensor = hass.states.get("binary_sensor.clip_presence_sensor")
    assert clip_presence_sensor is None

    vibration_sensor = hass.states.get("binary_sensor.vibration_sensor")
    assert vibration_sensor.state == "on"

    gateway.api.sensors["1"].async_update({"state": {"presence": True}})
    await hass.async_block_till_done()

    presence_sensor = hass.states.get("binary_sensor.presence_sensor")
    assert presence_sensor.state == "on"


async def test_allow_clip_sensor(hass):
    """Test that CLIP sensors can be allowed."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = deepcopy(SENSORS)
    gateway = await setup_deconz_integration(
        hass,
        ENTRY_CONFIG,
        options={deconz.gateway.CONF_ALLOW_CLIP_SENSOR: True},
        get_state_response=data,
    )
    assert "binary_sensor.presence_sensor" in gateway.deconz_ids
    assert "binary_sensor.temperature_sensor" not in gateway.deconz_ids
    assert "binary_sensor.clip_presence_sensor" in gateway.deconz_ids
    assert "binary_sensor.vibration_sensor" in gateway.deconz_ids
    assert len(hass.states.async_all()) == 4

    presence_sensor = hass.states.get("binary_sensor.presence_sensor")
    assert presence_sensor.state == "off"

    temperature_sensor = hass.states.get("binary_sensor.temperature_sensor")
    assert temperature_sensor is None

    clip_presence_sensor = hass.states.get("binary_sensor.clip_presence_sensor")
    assert clip_presence_sensor.state == "off"

    vibration_sensor = hass.states.get("binary_sensor.vibration_sensor")
    assert vibration_sensor.state == "on"


async def test_add_new_binary_sensor(hass):
    """Test that adding a new binary sensor works."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    gateway = await setup_deconz_integration(
        hass, ENTRY_CONFIG, options={}, get_state_response=data
    )
    assert len(gateway.deconz_ids) == 0

    state_added = {
        "t": "event",
        "e": "added",
        "r": "sensors",
        "id": "1",
        "sensor": deepcopy(SENSORS["1"]),
    }
    gateway.api.async_event_handler(state_added)
    await hass.async_block_till_done()

    assert "binary_sensor.presence_sensor" in gateway.deconz_ids

    presence_sensor = hass.states.get("binary_sensor.presence_sensor")
    assert presence_sensor.state == "off"
