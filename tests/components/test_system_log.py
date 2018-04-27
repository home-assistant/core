"""Test system log component."""
import logging
from unittest.mock import MagicMock, patch

from homeassistant.core import callback
from homeassistant.bootstrap import async_setup_component
from homeassistant.components import system_log

_LOGGER = logging.getLogger('test_logger')
BASIC_CONFIG = {
    'system_log': {
        'max_entries': 2,
    }
}


async def get_error_log(hass, aiohttp_client, expected_count):
    """Fetch all entries from system_log via the API."""
    client = await aiohttp_client(hass.http.app)
    resp = await client.get('/api/error/all')
    assert resp.status == 200

    data = await resp.json()
    assert len(data) == expected_count
    return data


def _generate_and_log_exception(exception, log):
    try:
        raise Exception(exception)
    except:  # noqa: E722  # pylint: disable=bare-except
        _LOGGER.exception(log)


def assert_log(log, exception, message, level):
    """Assert that specified values are in a specific log entry."""
    assert exception in log['exception']
    assert message == log['message']
    assert level == log['level']
    assert 'timestamp' in log


def get_frame(name):
    """Get log stack frame."""
    return (name, None, None, None)


async def test_normal_logs(hass, aiohttp_client):
    """Test that debug and info are not logged."""
    await async_setup_component(hass, system_log.DOMAIN, BASIC_CONFIG)
    _LOGGER.debug('debug')
    _LOGGER.info('info')

    # Assert done by get_error_log
    await get_error_log(hass, aiohttp_client, 0)


async def test_exception(hass, aiohttp_client):
    """Test that exceptions are logged and retrieved correctly."""
    await async_setup_component(hass, system_log.DOMAIN, BASIC_CONFIG)
    _generate_and_log_exception('exception message', 'log message')
    log = (await get_error_log(hass, aiohttp_client, 1))[0]
    assert_log(log, 'exception message', 'log message', 'ERROR')


async def test_warning(hass, aiohttp_client):
    """Test that warning are logged and retrieved correctly."""
    await async_setup_component(hass, system_log.DOMAIN, BASIC_CONFIG)
    _LOGGER.warning('warning message')
    log = (await get_error_log(hass, aiohttp_client, 1))[0]
    assert_log(log, '', 'warning message', 'WARNING')


async def test_error(hass, aiohttp_client):
    """Test that errors are logged and retrieved correctly."""
    await async_setup_component(hass, system_log.DOMAIN, BASIC_CONFIG)
    _LOGGER.error('error message')
    log = (await get_error_log(hass, aiohttp_client, 1))[0]
    assert_log(log, '', 'error message', 'ERROR')


async def test_config_not_fire_event(hass):
    """Test that errors are not posted as events with default config."""
    await async_setup_component(hass, system_log.DOMAIN, BASIC_CONFIG)
    events = []

    @callback
    def event_listener(event):
        """Listen to events of type system_log_event."""
        events.append(event)

    hass.bus.async_listen(system_log.EVENT_SYSTEM_LOG, event_listener)

    _LOGGER.error('error message')
    await hass.async_block_till_done()

    assert len(events) == 0


async def test_error_posted_as_event(hass):
    """Test that error are posted as events."""
    await async_setup_component(hass, system_log.DOMAIN, {
        'system_log': {
            'max_entries': 2,
            'fire_event': True,
        }
    })
    events = []

    @callback
    def event_listener(event):
        """Listen to events of type system_log_event."""
        events.append(event)

    hass.bus.async_listen(system_log.EVENT_SYSTEM_LOG, event_listener)

    _LOGGER.error('error message')
    await hass.async_block_till_done()

    assert len(events) == 1
    assert_log(events[0].data, '', 'error message', 'ERROR')


async def test_critical(hass, aiohttp_client):
    """Test that critical are logged and retrieved correctly."""
    await async_setup_component(hass, system_log.DOMAIN, BASIC_CONFIG)
    _LOGGER.critical('critical message')
    log = (await get_error_log(hass, aiohttp_client, 1))[0]
    assert_log(log, '', 'critical message', 'CRITICAL')


async def test_remove_older_logs(hass, aiohttp_client):
    """Test that older logs are rotated out."""
    await async_setup_component(hass, system_log.DOMAIN, BASIC_CONFIG)
    _LOGGER.error('error message 1')
    _LOGGER.error('error message 2')
    _LOGGER.error('error message 3')
    log = await get_error_log(hass, aiohttp_client, 2)
    assert_log(log[0], '', 'error message 3', 'ERROR')
    assert_log(log[1], '', 'error message 2', 'ERROR')


async def test_clear_logs(hass, aiohttp_client):
    """Test that the log can be cleared via a service call."""
    await async_setup_component(hass, system_log.DOMAIN, BASIC_CONFIG)
    _LOGGER.error('error message')

    hass.async_add_job(
        hass.services.async_call(
            system_log.DOMAIN, system_log.SERVICE_CLEAR, {}))
    await hass.async_block_till_done()

    # Assert done by get_error_log
    await get_error_log(hass, aiohttp_client, 0)


async def test_write_log(hass):
    """Test that error propagates to logger."""
    await async_setup_component(hass, system_log.DOMAIN, BASIC_CONFIG)
    logger = MagicMock()
    with patch('logging.getLogger', return_value=logger) as mock_logging:
        hass.async_add_job(
            hass.services.async_call(
                system_log.DOMAIN, system_log.SERVICE_WRITE,
                {'message': 'test_message'}))
        await hass.async_block_till_done()
    mock_logging.assert_called_once_with(
        'homeassistant.components.system_log.external')
    assert logger.method_calls[0] == ('error', ('test_message',))


async def test_write_choose_logger(hass):
    """Test that correct logger is chosen."""
    await async_setup_component(hass, system_log.DOMAIN, BASIC_CONFIG)
    with patch('logging.getLogger') as mock_logging:
        hass.async_add_job(
            hass.services.async_call(
                system_log.DOMAIN, system_log.SERVICE_WRITE,
                {'message': 'test_message',
                 'logger': 'myLogger'}))
        await hass.async_block_till_done()
    mock_logging.assert_called_once_with(
        'myLogger')


async def test_write_choose_level(hass):
    """Test that correct logger is chosen."""
    await async_setup_component(hass, system_log.DOMAIN, BASIC_CONFIG)
    logger = MagicMock()
    with patch('logging.getLogger', return_value=logger):
        hass.async_add_job(
            hass.services.async_call(
                system_log.DOMAIN, system_log.SERVICE_WRITE,
                {'message': 'test_message',
                 'level': 'debug'}))
        await hass.async_block_till_done()
    assert logger.method_calls[0] == ('debug', ('test_message',))


async def test_unknown_path(hass, aiohttp_client):
    """Test error logged from unknown path."""
    await async_setup_component(hass, system_log.DOMAIN, BASIC_CONFIG)
    _LOGGER.findCaller = MagicMock(
        return_value=('unknown_path', 0, None, None))
    _LOGGER.error('error message')
    log = (await get_error_log(hass, aiohttp_client, 1))[0]
    assert log['source'] == 'unknown_path'


def log_error_from_test_path(path):
    """Log error while mocking the path."""
    call_path = 'internal_path.py'
    with patch.object(_LOGGER,
                      'findCaller',
                      MagicMock(return_value=(call_path, 0, None, None))):
        with patch('traceback.extract_stack',
                   MagicMock(return_value=[
                       get_frame('main_path/main.py'),
                       get_frame(path),
                       get_frame(call_path),
                       get_frame('venv_path/logging/log.py')])):
            _LOGGER.error('error message')


async def test_homeassistant_path(hass, aiohttp_client):
    """Test error logged from homeassistant path."""
    await async_setup_component(hass, system_log.DOMAIN, BASIC_CONFIG)
    with patch('homeassistant.components.system_log.HOMEASSISTANT_PATH',
               new=['venv_path/homeassistant']):
        log_error_from_test_path(
            'venv_path/homeassistant/component/component.py')
        log = (await get_error_log(hass, aiohttp_client, 1))[0]
    assert log['source'] == 'component/component.py'


async def test_config_path(hass, aiohttp_client):
    """Test error logged from config path."""
    await async_setup_component(hass, system_log.DOMAIN, BASIC_CONFIG)
    with patch.object(hass.config, 'config_dir', new='config'):
        log_error_from_test_path('config/custom_component/test.py')
        log = (await get_error_log(hass, aiohttp_client, 1))[0]
    assert log['source'] == 'custom_component/test.py'


async def test_netdisco_path(hass, aiohttp_client):
    """Test error logged from netdisco path."""
    await async_setup_component(hass, system_log.DOMAIN, BASIC_CONFIG)
    with patch.dict('sys.modules',
                    netdisco=MagicMock(__path__=['venv_path/netdisco'])):
        log_error_from_test_path('venv_path/netdisco/disco_component.py')
        log = (await get_error_log(hass, aiohttp_client, 1))[0]
    assert log['source'] == 'disco_component.py'
