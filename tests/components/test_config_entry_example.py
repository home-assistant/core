"""Test the config entry example component."""
import asyncio

from homeassistant import config_entries


@asyncio.coroutine
def test_flow_works(hass):
    """Test that the config flow works."""
    result = yield from hass.config_entries.flow.async_init(
        'config_entry_example')

    assert result['type'] == config_entries.RESULT_TYPE_FORM

    result = yield from hass.config_entries.flow.async_configure(
        result['flow_id'], {
            'object_id': 'bla'
        })

    assert result['type'] == config_entries.RESULT_TYPE_FORM

    result = yield from hass.config_entries.flow.async_configure(
        result['flow_id'], {
            'name': 'Hello'
        })

    assert result['type'] == config_entries.RESULT_TYPE_CREATE_ENTRY
    state = hass.states.get('config_entry_example.bla')
    assert state is not None
    assert state.name == 'Hello'
    assert 'config_entry_example' in hass.config.components
    assert len(hass.config_entries.async_entries()) == 1

    # Test removing entry.
    entry = hass.config_entries.async_entries()[0]
    yield from hass.config_entries.async_remove(entry.entry_id)
    state = hass.states.get('config_entry_example.bla')
    assert state is None
