"""deCONZ sensor platform tests."""
from unittest.mock import Mock, patch


from homeassistant import config_entries
from homeassistant.components import deconz
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import mock_coro


SENSOR = {
    "1": {
        "id": "Sensor 1 id",
        "name": "Sensor 1 name",
        "type": "ZHATemperature",
        "state": {"temperature": False},
        "config": {}
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
        "config": {"battery": 100}
    }
}


async def setup_bridge(hass, data, allow_clip_sensor=True):
    """Load the deCONZ sensor platform."""
    from pydeconz import DeconzSession
    loop = Mock()
    session = Mock()
    entry = Mock()
    entry.data = {'host': '1.2.3.4', 'port': 80, 'api_key': '1234567890ABCDEF'}
    bridge = DeconzSession(loop, session, **entry.data)
    with patch('pydeconz.DeconzSession.async_get_state',
               return_value=mock_coro(data)):
        await bridge.async_load_parameters()
    hass.data[deconz.DOMAIN] = bridge
    hass.data[deconz.DATA_DECONZ_UNSUB] = []
    hass.data[deconz.DATA_DECONZ_EVENT] = []
    hass.data[deconz.DATA_DECONZ_ID] = {}
    config_entry = config_entries.ConfigEntry(
        1, deconz.DOMAIN, 'Mock Title',
        {'host': 'mock-host', 'allow_clip_sensor': allow_clip_sensor}, 'test')
    await hass.config_entries.async_forward_entry_setup(config_entry, 'sensor')
    # To flush out the service call to update the group
    await hass.async_block_till_done()


async def test_no_sensors(hass):
    """Test that no sensors in deconz results in no sensor entities."""
    data = {}
    await setup_bridge(hass, data)
    assert len(hass.data[deconz.DATA_DECONZ_ID]) == 0
    assert len(hass.states.async_all()) == 0


async def test_sensors(hass):
    """Test successful creation of sensor entities."""
    data = {"sensors": SENSOR}
    await setup_bridge(hass, data)
    assert "sensor.sensor_1_name" in hass.data[deconz.DATA_DECONZ_ID]
    assert "sensor.sensor_2_name" not in hass.data[deconz.DATA_DECONZ_ID]
    assert "sensor.sensor_3_name" not in hass.data[deconz.DATA_DECONZ_ID]
    assert "sensor.sensor_3_name_battery_level" not in \
        hass.data[deconz.DATA_DECONZ_ID]
    assert "sensor.sensor_4_name" not in hass.data[deconz.DATA_DECONZ_ID]
    assert "sensor.sensor_4_name_battery_level" in \
        hass.data[deconz.DATA_DECONZ_ID]
    assert len(hass.states.async_all()) == 2


async def test_add_new_sensor(hass):
    """Test successful creation of sensor entities."""
    data = {}
    await setup_bridge(hass, data)
    sensor = Mock()
    sensor.name = 'name'
    sensor.type = 'ZHATemperature'
    sensor.register_async_callback = Mock()
    async_dispatcher_send(hass, 'deconz_new_sensor', [sensor])
    await hass.async_block_till_done()
    assert "sensor.name" in hass.data[deconz.DATA_DECONZ_ID]


async def test_do_not_allow_clipsensor(hass):
    """Test that clip sensors can be ignored."""
    data = {}
    await setup_bridge(hass, data, allow_clip_sensor=False)
    sensor = Mock()
    sensor.name = 'name'
    sensor.type = 'CLIPTemperature'
    sensor.register_async_callback = Mock()
    async_dispatcher_send(hass, 'deconz_new_sensor', [sensor])
    await hass.async_block_till_done()
    assert len(hass.data[deconz.DATA_DECONZ_ID]) == 0
