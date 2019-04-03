"""deCONZ climate platform tests."""
from unittest.mock import Mock, patch

import asynctest

from homeassistant import config_entries
from homeassistant.components import deconz
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

import homeassistant.components.climate as climate

from tests.common import mock_coro


SENSOR = {
    "1": {
        "id": "Climate 1 id",
        "name": "Climate 1 name",
        "type": "ZHAThermostat",
        "state": {"on": True, "temperature": 2260},
        "config": {"battery": 100, "heatsetpoint": 2200, "mode": "auto",
                   "offset": 10, "reachable": True, "valve": 30},
        "uniqueid": "00:00:00:00:00:00:00:00-00"
    },
    "2": {
        "id": "Sensor 2 id",
        "name": "Sensor 2 name",
        "type": "ZHAPresence",
        "state": {"presence": False},
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
    """Load the deCONZ sensor platform."""
    from pydeconz import DeconzSession

    response = Mock(
        status=200, json=asynctest.CoroutineMock(),
        text=asynctest.CoroutineMock())
    response.content_type = 'application/json'

    session = Mock(
        put=asynctest.CoroutineMock(
            return_value=response
        )
    )

    ENTRY_CONFIG[deconz.const.CONF_ALLOW_CLIP_SENSOR] = allow_clip_sensor

    config_entry = config_entries.ConfigEntry(
        1, deconz.DOMAIN, 'Mock Title', ENTRY_CONFIG, 'test',
        config_entries.CONN_CLASS_LOCAL_PUSH)
    gateway = deconz.DeconzGateway(hass, config_entry)
    gateway.api = DeconzSession(hass.loop, session, **config_entry.data)
    gateway.api.config = Mock()
    hass.data[deconz.DOMAIN] = gateway

    with patch('pydeconz.DeconzSession.async_get_state',
               return_value=mock_coro(data)):
        await gateway.api.async_load_parameters()

    await hass.config_entries.async_forward_entry_setup(
        config_entry, 'climate')
    # To flush out the service call to update the group
    await hass.async_block_till_done()


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a gateway."""
    assert await async_setup_component(hass, climate.DOMAIN, {
        'climate': {
            'platform': deconz.DOMAIN
        }
    }) is True
    assert deconz.DOMAIN not in hass.data


async def test_no_sensors(hass):
    """Test that no sensors in deconz results in no climate entities."""
    await setup_gateway(hass, {})
    assert not hass.data[deconz.DOMAIN].deconz_ids
    assert not hass.states.async_all()


async def test_climate_devices(hass):
    """Test successful creation of sensor entities."""
    await setup_gateway(hass, {"sensors": SENSOR})
    assert "climate.climate_1_name" in hass.data[deconz.DOMAIN].deconz_ids
    assert "sensor.sensor_2_name" not in hass.data[deconz.DOMAIN].deconz_ids
    assert len(hass.states.async_all()) == 1

    hass.data[deconz.DOMAIN].api.sensors['1'].async_update(
        {'state': {'on': False}})

    await hass.services.async_call(
        'climate', 'turn_on', {'entity_id': 'climate.climate_1_name'},
        blocking=True
    )
    hass.data[deconz.DOMAIN].api.session.put.assert_called_with(
        'http://1.2.3.4:80/api/ABCDEF/sensors/1/config',
        data='{"mode": "auto"}'
    )

    await hass.services.async_call(
        'climate', 'turn_off', {'entity_id': 'climate.climate_1_name'},
        blocking=True
    )
    hass.data[deconz.DOMAIN].api.session.put.assert_called_with(
        'http://1.2.3.4:80/api/ABCDEF/sensors/1/config',
        data='{"mode": "off"}'
    )

    await hass.services.async_call(
        'climate', 'set_temperature',
        {'entity_id': 'climate.climate_1_name', 'temperature': 20},
        blocking=True
    )
    hass.data[deconz.DOMAIN].api.session.put.assert_called_with(
        'http://1.2.3.4:80/api/ABCDEF/sensors/1/config',
        data='{"heatsetpoint": 2000.0}'
    )

    assert len(hass.data[deconz.DOMAIN].api.session.put.mock_calls) == 3


async def test_verify_state_update(hass):
    """Test that state update properly."""
    await setup_gateway(hass, {"sensors": SENSOR})
    assert "climate.climate_1_name" in hass.data[deconz.DOMAIN].deconz_ids

    thermostat = hass.states.get('climate.climate_1_name')
    assert thermostat.state == 'on'

    state_update = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "config": {"on": False}
    }
    hass.data[deconz.DOMAIN].api.async_event_handler(state_update)

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    thermostat = hass.states.get('climate.climate_1_name')
    assert thermostat.state == 'off'


async def test_add_new_climate_device(hass):
    """Test successful creation of climate entities."""
    await setup_gateway(hass, {})
    sensor = Mock()
    sensor.name = 'name'
    sensor.type = 'ZHAThermostat'
    sensor.register_async_callback = Mock()
    async_dispatcher_send(hass, 'deconz_new_sensor', [sensor])
    await hass.async_block_till_done()
    assert "climate.name" in hass.data[deconz.DOMAIN].deconz_ids


async def test_do_not_allow_clipsensor(hass):
    """Test that clip sensors can be ignored."""
    await setup_gateway(hass, {}, allow_clip_sensor=False)
    sensor = Mock()
    sensor.name = 'name'
    sensor.type = 'CLIPThermostat'
    sensor.register_async_callback = Mock()
    async_dispatcher_send(hass, 'deconz_new_sensor', [sensor])
    await hass.async_block_till_done()
    assert len(hass.data[deconz.DOMAIN].deconz_ids) == 0


async def test_unload_sensor(hass):
    """Test that it works to unload sensor entities."""
    await setup_gateway(hass, {"sensors": SENSOR})

    await hass.data[deconz.DOMAIN].async_reset()

    assert len(hass.states.async_all()) == 0
