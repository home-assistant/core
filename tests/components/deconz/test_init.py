"""Test deCONZ component setup process."""
from unittest.mock import Mock, patch

from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component
from homeassistant.components import deconz

from tests.common import mock_coro

CONFIG = {
    "config": {
        "bridgeid": "0123456789ABCDEF",
        "mac": "12:34:56:78:90:ab",
        "modelid": "deCONZ",
        "name": "Phoscon",
        "swversion": "2.05.35"
    }
}


async def test_config_with_host_passed_to_config_entry(hass):
    """Test that configured options for a host are loaded via config entry."""
    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(deconz, 'configured_hosts', return_value=[]), \
            patch.object(deconz, 'load_json', return_value={}):
        assert await async_setup_component(hass, deconz.DOMAIN, {
            deconz.DOMAIN: {
                deconz.CONF_HOST: '1.2.3.4',
                deconz.CONF_PORT: 80
            }
        }) is True
    # Import flow started
    assert len(mock_config_entries.flow.mock_calls) == 2


async def test_config_file_passed_to_config_entry(hass):
    """Test that configuration file for a host are loaded via config entry."""
    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(deconz, 'configured_hosts', return_value=[]), \
            patch.object(deconz, 'load_json',
                         return_value={'host': '1.2.3.4'}):
        assert await async_setup_component(hass, deconz.DOMAIN, {
            deconz.DOMAIN: {}
        }) is True
    # Import flow started
    assert len(mock_config_entries.flow.mock_calls) == 2


async def test_config_without_host_not_passed_to_config_entry(hass):
    """Test that a configuration without a host does not initiate an import."""
    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(deconz, 'configured_hosts', return_value=[]), \
            patch.object(deconz, 'load_json', return_value={}):
        assert await async_setup_component(hass, deconz.DOMAIN, {
            deconz.DOMAIN: {}
        }) is True
    # No flow started
    assert len(mock_config_entries.flow.mock_calls) == 0


async def test_config_already_registered_not_passed_to_config_entry(hass):
    """Test that an already registered host does not initiate an import."""
    with patch.object(hass, 'config_entries') as mock_config_entries, \
            patch.object(deconz, 'configured_hosts',
                         return_value=['1.2.3.4']), \
            patch.object(deconz, 'load_json', return_value={}):
        assert await async_setup_component(hass, deconz.DOMAIN, {
            deconz.DOMAIN: {
                deconz.CONF_HOST: '1.2.3.4',
                deconz.CONF_PORT: 80
            }
        }) is True
    # No flow started
    assert len(mock_config_entries.flow.mock_calls) == 0


async def test_config_discovery(hass):
    """Test that a discovered bridge does not initiate an import."""
    with patch.object(hass, 'config_entries') as mock_config_entries:
        assert await async_setup_component(hass, deconz.DOMAIN, {}) is True
    # No flow started
    assert len(mock_config_entries.flow.mock_calls) == 0


async def test_setup_entry_already_registered_bridge(hass):
    """Test setup entry doesn't allow more than one instance of deCONZ."""
    hass.data[deconz.DOMAIN] = True
    assert await deconz.async_setup_entry(hass, {}) is False


async def test_setup_entry_no_available_bridge(hass):
    """Test setup entry fails if deCONZ is not available."""
    entry = Mock()
    entry.data = {'host': '1.2.3.4', 'port': 80, 'api_key': '1234567890ABCDEF'}
    with patch('pydeconz.DeconzSession.async_load_parameters',
               return_value=mock_coro(False)):
        assert await deconz.async_setup_entry(hass, entry) is False


async def test_setup_entry_successful(hass):
    """Test setup entry is successful."""
    entry = Mock()
    entry.data = {'host': '1.2.3.4', 'port': 80, 'api_key': '1234567890ABCDEF'}
    with patch.object(hass, 'async_create_task') as mock_add_job, \
        patch.object(hass, 'config_entries') as mock_config_entries, \
        patch('pydeconz.DeconzSession.async_get_state',
              return_value=mock_coro(CONFIG)), \
        patch('pydeconz.DeconzSession.start', return_value=True), \
        patch('homeassistant.helpers.device_registry.async_get_registry',
              return_value=mock_coro(Mock())):
        assert await deconz.async_setup_entry(hass, entry) is True
    assert hass.data[deconz.DOMAIN]
    assert hass.data[deconz.DATA_DECONZ_ID] == {}
    assert len(hass.data[deconz.DATA_DECONZ_UNSUB]) == 1
    assert len(mock_add_job.mock_calls) ==  \
        len(deconz.SUPPORTED_PLATFORMS)
    assert len(mock_config_entries.async_forward_entry_setup.mock_calls) == \
        len(deconz.SUPPORTED_PLATFORMS)
    assert mock_config_entries.async_forward_entry_setup.mock_calls[0][1] == \
        (entry, 'binary_sensor')
    assert mock_config_entries.async_forward_entry_setup.mock_calls[1][1] == \
        (entry, 'cover')
    assert mock_config_entries.async_forward_entry_setup.mock_calls[2][1] == \
        (entry, 'light')
    assert mock_config_entries.async_forward_entry_setup.mock_calls[3][1] == \
        (entry, 'scene')
    assert mock_config_entries.async_forward_entry_setup.mock_calls[4][1] == \
        (entry, 'sensor')
    assert mock_config_entries.async_forward_entry_setup.mock_calls[5][1] == \
        (entry, 'switch')


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    entry = Mock()
    entry.data = {'host': '1.2.3.4', 'port': 80, 'api_key': '1234567890ABCDEF'}
    entry.async_unload.return_value = mock_coro(True)
    deconzmock = Mock()
    deconzmock.async_load_parameters.return_value = mock_coro(True)
    deconzmock.sensors = {}
    with patch('pydeconz.DeconzSession', return_value=deconzmock):
        assert await deconz.async_setup_entry(hass, entry) is True

    assert deconz.DATA_DECONZ_EVENT in hass.data

    hass.data[deconz.DATA_DECONZ_EVENT].append(Mock())
    hass.data[deconz.DATA_DECONZ_ID] = {'id': 'deconzid'}
    assert await deconz.async_unload_entry(hass, entry)
    assert deconz.DOMAIN not in hass.data
    assert len(hass.data[deconz.DATA_DECONZ_UNSUB]) == 0
    assert len(hass.data[deconz.DATA_DECONZ_EVENT]) == 0
    assert len(hass.data[deconz.DATA_DECONZ_ID]) == 0


async def test_add_new_device(hass):
    """Test adding a new device generates a signal for platforms."""
    entry = Mock()
    entry.data = {'host': '1.2.3.4', 'port': 80,
                  'api_key': '1234567890ABCDEF', 'allow_clip_sensor': False}
    new_event = {
        "t": "event",
        "e": "added",
        "r": "sensors",
        "id": "1",
        "sensor": {
            "config": {
                "on": "True",
                "reachable": "True"
            },
            "name": "event",
            "state": {},
            "type": "ZHASwitch"
        }
    }
    with patch.object(deconz, 'async_dispatcher_send') as mock_dispatch_send, \
            patch('pydeconz.DeconzSession.async_get_state',
                  return_value=mock_coro(CONFIG)), \
            patch('pydeconz.DeconzSession.start', return_value=True):
        assert await deconz.async_setup_entry(hass, entry) is True
        hass.data[deconz.DOMAIN].async_event_handler(new_event)
        await hass.async_block_till_done()
        assert len(mock_dispatch_send.mock_calls) == 1
        assert len(mock_dispatch_send.mock_calls[0]) == 3


async def test_add_new_remote(hass):
    """Test new added device creates a new remote."""
    entry = Mock()
    entry.data = {'host': '1.2.3.4', 'port': 80,
                  'api_key': '1234567890ABCDEF', 'allow_clip_sensor': False}
    remote = Mock()
    remote.name = 'name'
    remote.type = 'ZHASwitch'
    remote.register_async_callback = Mock()
    with patch('pydeconz.DeconzSession.async_get_state',
               return_value=mock_coro(CONFIG)), \
            patch('pydeconz.DeconzSession.start', return_value=True):
        assert await deconz.async_setup_entry(hass, entry) is True
    async_dispatcher_send(hass, 'deconz_new_sensor', [remote])
    await hass.async_block_till_done()
    assert len(hass.data[deconz.DATA_DECONZ_EVENT]) == 1


async def test_do_not_allow_clip_sensor(hass):
    """Test that clip sensors can be ignored."""
    entry = Mock()
    entry.data = {'host': '1.2.3.4', 'port': 80,
                  'api_key': '1234567890ABCDEF', 'allow_clip_sensor': False}
    remote = Mock()
    remote.name = 'name'
    remote.type = 'CLIPSwitch'
    remote.register_async_callback = Mock()
    with patch('pydeconz.DeconzSession.async_get_state',
               return_value=mock_coro(CONFIG)), \
            patch('pydeconz.DeconzSession.start', return_value=True):
        assert await deconz.async_setup_entry(hass, entry) is True

    async_dispatcher_send(hass, 'deconz_new_sensor', [remote])
    await hass.async_block_till_done()
    assert len(hass.data[deconz.DATA_DECONZ_EVENT]) == 0
