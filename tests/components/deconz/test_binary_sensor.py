"""deCONZ binary sensor platform tests."""
from unittest.mock import Mock, patch

from homeassistant import config_entries
from homeassistant.components import deconz
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

import homeassistant.components.binary_sensor as binary_sensor

from tests.common import mock_coro


SENSOR = {
    "1": {
        "id": "Sensor 1 id",
        "name": "Sensor 1 name",
        "type": "ZHAPresence",
        "state": {"presence": False},
        "config": {},
        "uniqueid": "00:00:00:00:00:00:00:00-00"
    },
    "2": {
        "id": "Sensor 2 id",
        "name": "Sensor 2 name",
        "type": "ZHATemperature",
        "state": {"temperature": False},
        "config": {}
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
    """Load the deCONZ binary sensor platform."""
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
        config_entry, 'binary_sensor')
    # To flush out the service call to update the group
    await hass.async_block_till_done()


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a gateway."""
    assert await async_setup_component(hass, binary_sensor.DOMAIN, {
        'binary_sensor': {
            'platform': deconz.DOMAIN
        }
    }) is True
    assert deconz.DOMAIN not in hass.data


async def test_no_binary_sensors(hass):
    """Test that no sensors in deconz results in no sensor entities."""
    data = {}
    await setup_gateway(hass, data)
    assert len(hass.data[deconz.DOMAIN].deconz_ids) == 0
    assert len(hass.states.async_all()) == 0


async def test_binary_sensors(hass):
    """Test successful creation of binary sensor entities."""
    data = {"sensors": SENSOR}
    await setup_gateway(hass, data)
    assert "binary_sensor.sensor_1_name" in \
        hass.data[deconz.DOMAIN].deconz_ids
    assert "binary_sensor.sensor_2_name" not in \
        hass.data[deconz.DOMAIN].deconz_ids
    assert len(hass.states.async_all()) == 1

    hass.data[deconz.DOMAIN].api.sensors['1'].async_update(
        {'state': {'on': False}})


async def test_add_new_sensor(hass):
    """Test successful creation of sensor entities."""
    data = {}
    await setup_gateway(hass, data)
    sensor = Mock()
    sensor.name = 'name'
    sensor.type = 'ZHAPresence'
    sensor.register_async_callback = Mock()
    async_dispatcher_send(hass, 'deconz_new_sensor', [sensor])
    await hass.async_block_till_done()
    assert "binary_sensor.name" in hass.data[deconz.DOMAIN].deconz_ids


async def test_do_not_allow_clip_sensor(hass):
    """Test that clip sensors can be ignored."""
    data = {}
    await setup_gateway(hass, data, allow_clip_sensor=False)
    sensor = Mock()
    sensor.name = 'name'
    sensor.type = 'CLIPPresence'
    sensor.register_async_callback = Mock()
    async_dispatcher_send(hass, 'deconz_new_sensor', [sensor])
    await hass.async_block_till_done()
    assert len(hass.data[deconz.DOMAIN].deconz_ids) == 0


async def test_unload_switch(hass):
    """Test that it works to unload switch entities."""
    data = {"sensors": SENSOR}
    await setup_gateway(hass, data)

    await hass.data[deconz.DOMAIN].async_reset()

    assert len(hass.states.async_all()) == 0
