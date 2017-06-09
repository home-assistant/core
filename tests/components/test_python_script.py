"""Test the python_script component."""
import asyncio
import logging
from unittest.mock import patch, mock_open

from homeassistant.setup import async_setup_component
from homeassistant.components.python_script import execute


@asyncio.coroutine
def test_setup(hass):
    """Test we can discover scripts."""
    scripts = [
        '/some/config/dir/python_scripts/hello.py',
        '/some/config/dir/python_scripts/world_beer.py'
    ]
    with patch('homeassistant.components.python_script.os.path.isdir',
               return_value=True), \
            patch('homeassistant.components.python_script.glob.iglob',
                  return_value=scripts):
        res = yield from async_setup_component(hass, 'python_script', {})

    assert res
    assert hass.services.has_service('python_script', 'hello')
    assert hass.services.has_service('python_script', 'world_beer')

    with patch('homeassistant.components.python_script.open',
               mock_open(read_data='fake source'), create=True), \
            patch('homeassistant.components.python_script.execute') as mock_ex:
        yield from hass.services.async_call(
            'python_script', 'hello', {'some': 'data'}, blocking=True)

    assert len(mock_ex.mock_calls) == 1
    hass, script, source, data = mock_ex.mock_calls[0][1]

    assert hass is hass
    assert script == 'hello.py'
    assert source == 'fake source'
    assert data == {'some': 'data'}


@asyncio.coroutine
def test_setup_fails_on_no_dir(hass, caplog):
    """Test we fail setup when no dir found."""
    with patch('homeassistant.components.python_script.os.path.isdir',
               return_value=False):
        res = yield from async_setup_component(hass, 'python_script', {})

    assert not res
    assert 'Folder python_scripts not found in config folder' in caplog.text


@asyncio.coroutine
def test_execute_with_data(hass, caplog):
    """Test executing a script."""
    caplog.set_level(logging.WARNING)
    source = """
hass.states.set('test.entity', data.get('name', 'not set'))
    """

    hass.async_add_job(execute, hass, 'test.py', source, {'name': 'paulus'})
    yield from hass.async_block_till_done()

    assert hass.states.is_state('test.entity', 'paulus')

    # No errors logged = good
    assert caplog.text == ''


@asyncio.coroutine
def test_execute_warns_print(hass, caplog):
    """Test print triggers warning."""
    caplog.set_level(logging.WARNING)
    source = """
print("This triggers warning.")
    """

    hass.async_add_job(execute, hass, 'test.py', source, {})
    yield from hass.async_block_till_done()

    assert "Don't use print() inside scripts." in caplog.text


@asyncio.coroutine
def test_execute_logging(hass, caplog):
    """Test logging works."""
    caplog.set_level(logging.INFO)
    source = """
logger.info('Logging from inside script')
    """

    hass.async_add_job(execute, hass, 'test.py', source, {})
    yield from hass.async_block_till_done()

    assert "Logging from inside script" in caplog.text


@asyncio.coroutine
def test_execute_compile_error(hass, caplog):
    """Test compile error logs error."""
    caplog.set_level(logging.ERROR)
    source = """
this is not valid Python
    """

    hass.async_add_job(execute, hass, 'test.py', source, {})
    yield from hass.async_block_till_done()

    assert "Error loading script test.py" in caplog.text


@asyncio.coroutine
def test_execute_runtime_error(hass, caplog):
    """Test compile error logs error."""
    caplog.set_level(logging.ERROR)
    source = """
raise Exception('boom')
    """

    hass.async_add_job(execute, hass, 'test.py', source, {})
    yield from hass.async_block_till_done()

    assert "Error executing script test.py" in caplog.text
