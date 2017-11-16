"""Test system log component."""
import asyncio
import logging
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
    assert log['source'] == 'unknown'  # always unkown in tests
    assert 'timestamp' in log


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
