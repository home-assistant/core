"""deCONZ binary sensor platform tests."""
from copy import deepcopy

from asynctest import patch

from homeassistant import config_entries
from homeassistant.components import deconz
from homeassistant.setup import async_setup_component

import homeassistant.components.binary_sensor as binary_sensor


SENSORS = {
    "1": {
        "id": "Sensor 1 id",
        "name": "Sensor 1 name",
        "type": "ZHAPresence",
        "state": {"dark": False, "presence": False},
        "config": {"on": True, "reachable": True, "temperature": 10},
        "uniqueid": "00:00:00:00:00:00:00:00-00",
    },
    "2": {
        "id": "Sensor 2 id",
        "name": "Sensor 2 name",
        "type": "ZHATemperature",
        "state": {"temperature": False},
        "config": {},
        "uniqueid": "00:00:00:00:00:00:00:01-00",
    },
    "3": {
        "id": "Sensor 3 id",
        "name": "Sensor 3 name",
        "type": "CLIPPresence",
        "state": {},
        "config": {},
        "uniqueid": "00:00:00:00:00:00:00:02-00",
    },
    "4": {
        "id": "Sensor 4 id",
        "name": "Sensor 4 name",
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
    assert len(hass.data[deconz.DOMAIN][gateway.bridgeid].deconz_ids) == 0
    assert len(hass.states.async_all()) == 0


async def test_binary_sensors(hass):
    """Test successful creation of binary sensor entities."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = deepcopy(SENSORS)
    gateway = await setup_deconz_integration(
        hass, ENTRY_CONFIG, options={}, get_state_response=data
    )
    assert "binary_sensor.sensor_1_name" in gateway.deconz_ids
    assert "binary_sensor.sensor_2_name" not in gateway.deconz_ids
    assert "binary_sensor.sensor_3_name" not in gateway.deconz_ids
    assert "binary_sensor.sensor_4_name" in gateway.deconz_ids
    assert len(hass.states.async_all()) == 3

    sensor_1 = hass.states.get("binary_sensor.sensor_1_name")
    assert sensor_1.state == "off"

    sensor_2 = hass.states.get("binary_sensor.sensor_2_name")
    assert sensor_2 is None

    sensor_3 = hass.states.get("binary_sensor.sensor_3_name")
    assert sensor_3 is None

    sensor_4 = hass.states.get("binary_sensor.sensor_4_name")
    assert sensor_4.state == "on"

    hass.data[deconz.DOMAIN][gateway.bridgeid].api.sensors["1"].async_update(
        {"state": {"presence": True}}
    )
    await hass.async_block_till_done()

    sensor_1 = hass.states.get("binary_sensor.sensor_1_name")
    assert sensor_1.state == "on"


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
    assert "binary_sensor.sensor_1_name" in gateway.deconz_ids
    assert "binary_sensor.sensor_2_name" not in gateway.deconz_ids
    assert "binary_sensor.sensor_3_name" in gateway.deconz_ids
    assert "binary_sensor.sensor_4_name" in gateway.deconz_ids
    assert len(hass.states.async_all()) == 4

    sensor_1 = hass.states.get("binary_sensor.sensor_1_name")
    assert sensor_1.state == "off"

    sensor_2 = hass.states.get("binary_sensor.sensor_2_name")
    assert sensor_2 is None

    sensor_3 = hass.states.get("binary_sensor.sensor_3_name")
    assert sensor_3 is not None
