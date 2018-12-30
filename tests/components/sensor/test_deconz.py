"""deCONZ sensor platform tests."""
from unittest.mock import Mock, patch

from homeassistant import config_entries
from homeassistant.components import deconz
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

import homeassistant.components.sensor as sensor

from tests.common import mock_coro


SENSOR = {
    "1": {
        "id": "Sensor 1 id",
        "name": "Sensor 1 name",
        "type": "ZHALightLevel",
        "state": {"lightlevel": 30000, "dark": False},
        "config": {"reachable": True},
        "uniqueid": "00:00:00:00:00:00:00:00-00"
    },
    "2": {
        "id": "Sensor 2 id",
        "name": "Sensor 2 name",
        "type": "ZHAPresence",
        "state": {"presence": False},
        "config": {}
    },
    "3": {
        "id": "Sensor 3 id",
        "name": "Sensor 3 name",
        "type": "ZHASwitch",
        "state": {"buttonevent": 1000},
        "config": {}
    },
    "4": {
        "id": "Sensor 4 id",
        "name": "Sensor 4 name",
        "type": "ZHASwitch",
        "state": {"buttonevent": 1000},
        "config": {"battery": 100},
        "uniqueid": "00:00:00:00:00:00:00:01-00"
    },
    "5": {
        "id": "Sensor 5 id",
        "name": "Sensor 5 name",
        "type": "ZHASwitch",
        "state": {"buttonevent": 1000},
        "config": {"battery": 100},
        "uniqueid": "00:00:00:00:00:00:00:02:00-00"
    },
    "6": {
        "id": "Sensor 6 id",
        "name": "Sensor 6 name",
        "type": "Daylight",
        "state": {"daylight": True},
        "config": {}
    },
    "7": {
        "id": "Sensor 7 id",
        "name": "Sensor 7 name",
        "type": "ZHAPower",
        "state": {"current": 2, "power": 6, "voltage": 3},
        "config": {"reachable": True}
    }
}


ENTRY_CONFIG = {
    deconz.const.CONF_ALLOW_CLIP_SENSOR: True,
    deconz.const.CONF_ALLOW_DECONZ_GROUPS: True,
    deconz.config_flow.CONF_API_KEY: "ABCDEF",
    deconz.config_flow.CONF_BRIDGEID: "0123456789",
    deconz.config_flow.CONF_HOST: "1.2.3.4",
    deconz.config_flow.CONF_PORT: 80
}


async def setup_gateway(hass, data, allow_clip_sensor=True):
    """Load the deCONZ sensor platform."""
    from pydeconz import DeconzSession
    loop = Mock()
    session = Mock()

    ENTRY_CONFIG[deconz.const.CONF_ALLOW_CLIP_SENSOR] = allow_clip_sensor

    config_entry = config_entries.ConfigEntry(
        1, deconz.DOMAIN, 'Mock Title', ENTRY_CONFIG, 'test',
        config_entries.CONN_CLASS_LOCAL_PUSH)
    gateway = deconz.DeconzGateway(hass, config_entry)
    gateway.api = DeconzSession(loop, session, **config_entry.data)
    gateway.api.config = Mock()
    hass.data[deconz.DOMAIN] = gateway

    with patch('pydeconz.DeconzSession.async_get_state',
               return_value=mock_coro(data)):
        await gateway.api.async_load_parameters()

    await hass.config_entries.async_forward_entry_setup(
        config_entry, 'sensor')
    # To flush out the service call to update the group
    await hass.async_block_till_done()


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a gateway."""
    assert await async_setup_component(hass, sensor.DOMAIN, {
        'sensor': {
            'platform': deconz.DOMAIN
        }
    }) is True
    assert deconz.DOMAIN not in hass.data


async def test_no_sensors(hass):
    """Test that no sensors in deconz results in no sensor entities."""
    await setup_gateway(hass, {})
    assert len(hass.data[deconz.DOMAIN].deconz_ids) == 0
    assert len(hass.states.async_all()) == 0


async def test_sensors(hass):
    """Test successful creation of sensor entities."""
    await setup_gateway(hass, {"sensors": SENSOR})
    assert "sensor.sensor_1_name" in hass.data[deconz.DOMAIN].deconz_ids
    assert "sensor.sensor_2_name" not in hass.data[deconz.DOMAIN].deconz_ids
    assert "sensor.sensor_3_name" not in hass.data[deconz.DOMAIN].deconz_ids
    assert "sensor.sensor_3_name_battery_level" not in \
        hass.data[deconz.DOMAIN].deconz_ids
    assert "sensor.sensor_4_name" not in hass.data[deconz.DOMAIN].deconz_ids
    assert "sensor.sensor_4_name_battery_level" in \
        hass.data[deconz.DOMAIN].deconz_ids
    assert len(hass.states.async_all()) == 5

    hass.data[deconz.DOMAIN].api.sensors['1'].async_update(
        {'state': {'on': False}})
    hass.data[deconz.DOMAIN].api.sensors['4'].async_update(
        {'config': {'battery': 75}})


async def test_add_new_sensor(hass):
    """Test successful creation of sensor entities."""
    await setup_gateway(hass, {})
    sensor = Mock()
    sensor.name = 'name'
    sensor.type = 'ZHATemperature'
    sensor.register_async_callback = Mock()
    async_dispatcher_send(hass, 'deconz_new_sensor', [sensor])
    await hass.async_block_till_done()
    assert "sensor.name" in hass.data[deconz.DOMAIN].deconz_ids


async def test_do_not_allow_clipsensor(hass):
    """Test that clip sensors can be ignored."""
    await setup_gateway(hass, {}, allow_clip_sensor=False)
    sensor = Mock()
    sensor.name = 'name'
    sensor.type = 'CLIPTemperature'
    sensor.register_async_callback = Mock()
    async_dispatcher_send(hass, 'deconz_new_sensor', [sensor])
    await hass.async_block_till_done()
    assert len(hass.data[deconz.DOMAIN].deconz_ids) == 0


async def test_unload_sensor(hass):
    """Test that it works to unload sensor entities."""
    await setup_gateway(hass, {"sensors": SENSOR})

    await hass.data[deconz.DOMAIN].async_reset()

    assert len(hass.states.async_all()) == 0
