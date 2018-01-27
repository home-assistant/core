"""Test system log component."""
import asyncio
import logging
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import system_log

_LOGGER = logging.getLogger('test_logger')


@pytest.fixture(autouse=True)
@asyncio.coroutine
def setup_test_case(hass):
    """Setup system_log component before test case."""
    config = {'system_log': {'max_entries': 2}}
    yield from async_setup_component(hass, system_log.DOMAIN, config)


@asyncio.coroutine
def get_error_log(hass, test_client, expected_count):
    """Fetch all entries from system_log via the API."""
    client = yield from test_client(hass.http.app)
    resp = yield from client.get('/api/error/all')
    assert resp.status == 200

    data = yield from resp.json()
    assert len(data) == expected_count
    return data


def _generate_and_log_exception(exception, log):
    try:
        raise Exception(exception)
    except:  # pylint: disable=bare-except
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


@asyncio.coroutine
def test_normal_logs(hass, test_client):
    """Test that debug and info are not logged."""
    _LOGGER.debug('debug')
    _LOGGER.info('info')

    # Assert done by get_error_log
    yield from get_error_log(hass, test_client, 0)


@asyncio.coroutine
def test_exception(hass, test_client):
    """Test that exceptions are logged and retrieved correctly."""
    _generate_and_log_exception('exception message', 'log message')
    log = (yield from get_error_log(hass, test_client, 1))[0]
    assert_log(log, 'exception message', 'log message', 'ERROR')


@asyncio.coroutine
def test_warning(hass, test_client):
    """Test that warning are logged and retrieved correctly."""
    _LOGGER.warning('warning message')
    log = (yield from get_error_log(hass, test_client, 1))[0]
    assert_log(log, '', 'warning message', 'WARNING')


@asyncio.coroutine
def test_error(hass, test_client):
    """Test that errors are logged and retrieved correctly."""
    _LOGGER.error('error message')
    log = (yield from get_error_log(hass, test_client, 1))[0]
    assert_log(log, '', 'error message', 'ERROR')


@asyncio.coroutine
def test_critical(hass, test_client):
    """Test that critical are logged and retrieved correctly."""
    _LOGGER.critical('critical message')
    log = (yield from get_error_log(hass, test_client, 1))[0]
    assert_log(log, '', 'critical message', 'CRITICAL')


@asyncio.coroutine
def test_remove_older_logs(hass, test_client):
    """Test that older logs are rotated out."""
    _LOGGER.error('error message 1')
    _LOGGER.error('error message 2')
    _LOGGER.error('error message 3')
    log = yield from get_error_log(hass, test_client, 2)
    assert_log(log[0], '', 'error message 3', 'ERROR')
    assert_log(log[1], '', 'error message 2', 'ERROR')


@asyncio.coroutine
def test_clear_logs(hass, test_client):
    """Test that the log can be cleared via a service call."""
    _LOGGER.error('error message')

    hass.async_add_job(
        hass.services.async_call(
            system_log.DOMAIN, system_log.SERVICE_CLEAR, {}))
    yield from hass.async_block_till_done()

    # Assert done by get_error_log
    yield from get_error_log(hass, test_client, 0)


@asyncio.coroutine
def test_write_log(hass):
    """Test that error propagates to logger."""
    logger = MagicMock()
    with patch('logging.getLogger', return_value=logger) as mock_logging:
        hass.async_add_job(
            hass.services.async_call(
                system_log.DOMAIN, system_log.SERVICE_WRITE,
                {'message': 'test_message'}))
        yield from hass.async_block_till_done()
    mock_logging.assert_called_once_with(
        'homeassistant.components.system_log.external')
    assert logger.method_calls[0] == ('error', ('test_message',))


@asyncio.coroutine
def test_write_choose_logger(hass):
    """Test that correct logger is chosen."""
    with patch('logging.getLogger') as mock_logging:
        hass.async_add_job(
            hass.services.async_call(
                system_log.DOMAIN, system_log.SERVICE_WRITE,
                {'message': 'test_message',
                 'logger': 'myLogger'}))
        yield from hass.async_block_till_done()
    mock_logging.assert_called_once_with(
        'myLogger')


@asyncio.coroutine
def test_write_choose_level(hass):
    """Test that correct logger is chosen."""
    logger = MagicMock()
    with patch('logging.getLogger', return_value=logger):
        hass.async_add_job(
            hass.services.async_call(
                system_log.DOMAIN, system_log.SERVICE_WRITE,
                {'message': 'test_message',
                 'level': 'debug'}))
        yield from hass.async_block_till_done()
    assert logger.method_calls[0] == ('debug', ('test_message',))


@asyncio.coroutine
def test_unknown_path(hass, test_client):
    """Test error logged from unknown path."""
    _LOGGER.findCaller = MagicMock(
        return_value=('unknown_path', 0, None, None))
    _LOGGER.error('error message')
    log = (yield from get_error_log(hass, test_client, 1))[0]
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


@asyncio.coroutine
def test_homeassistant_path(hass, test_client):
    """Test error logged from homeassistant path."""
    log_error_from_test_path('venv_path/homeassistant/component/component.py')

    with patch('homeassistant.components.system_log.HOMEASSISTANT_PATH',
               new=['venv_path/homeassistant']):
        log = (yield from get_error_log(hass, test_client, 1))[0]
    assert log['source'] == 'component/component.py'


@asyncio.coroutine
def test_config_path(hass, test_client):
    """Test error logged from config path."""
    log_error_from_test_path('config/custom_component/test.py')

    with patch.object(hass.config, 'config_dir', new='config'):
        log = (yield from get_error_log(hass, test_client, 1))[0]
    assert log['source'] == 'custom_component/test.py'


@asyncio.coroutine
def test_netdisco_path(hass, test_client):
    """Test error logged from netdisco path."""
    log_error_from_test_path('venv_path/netdisco/disco_component.py')

    with patch.dict('sys.modules',
                    netdisco=MagicMock(__path__=['venv_path/netdisco'])):
        log = (yield from get_error_log(hass, test_client, 1))[0]
    assert log['source'] == 'disco_component.py'
