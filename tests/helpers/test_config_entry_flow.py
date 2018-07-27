"""Tests for the Config Entry Flow helper."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow, loader
from homeassistant.helpers import config_entry_flow
from tests.common import MockConfigEntry, MockModule


@pytest.fixture
def flow_conf(hass):
    """Register a handler."""
    handler_conf = {
        'discovered': False,
    }

    async def has_discovered_devices(hass):
        """Mock if we have discovered devices."""
        return handler_conf['discovered']

    with patch.dict(config_entries.HANDLERS):
        config_entry_flow.register_discovery_flow(
            'test', 'Test', has_discovered_devices)
        yield handler_conf


async def test_single_entry_allowed(hass, flow_conf):
    """Test only a single entry is allowed."""
    flow = config_entries.HANDLERS['test']()
    flow.hass = hass

    MockConfigEntry(domain='test').add_to_hass(hass)
    result = await flow.async_step_init()

    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'single_instance_allowed'


async def test_user_no_devices_found(hass, flow_conf):
    """Test if no devices found."""
    flow = config_entries.HANDLERS['test']()
    flow.hass = hass

    result = await flow.async_step_init()

    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'no_devices_found'


async def test_user_no_confirmation(hass, flow_conf):
    """Test user requires no confirmation to setup."""
    flow = config_entries.HANDLERS['test']()
    flow.hass = hass
    flow_conf['discovered'] = True

    result = await flow.async_step_init()

    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_discovery_single_instance(hass, flow_conf):
    """Test we ask for confirmation via discovery."""
    flow = config_entries.HANDLERS['test']()
    flow.hass = hass

    MockConfigEntry(domain='test').add_to_hass(hass)
    result = await flow.async_step_discovery({})

    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'single_instance_allowed'


async def test_discovery_confirmation(hass, flow_conf):
    """Test we ask for confirmation via discovery."""
    flow = config_entries.HANDLERS['test']()
    flow.hass = hass

    result = await flow.async_step_discovery({})

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'confirm'

    result = await flow.async_step_confirm({})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_multiple_discoveries(hass, flow_conf):
    """Test we only create one instance for multiple discoveries."""
    loader.set_component(hass, 'test', MockModule('test'))

    result = await hass.config_entries.flow.async_init(
        'test', source=data_entry_flow.SOURCE_DISCOVERY, data={})
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM

    # Second discovery
    result = await hass.config_entries.flow.async_init(
        'test', source=data_entry_flow.SOURCE_DISCOVERY, data={})
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT


async def test_user_init_trumps_discovery(hass, flow_conf):
    """Test a user initialized one will finish and cancel discovered one."""
    loader.set_component(hass, 'test', MockModule('test'))

    # Discovery starts flow
    result = await hass.config_entries.flow.async_init(
        'test', source=data_entry_flow.SOURCE_DISCOVERY, data={})
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM

    # User starts flow
    result = await hass.config_entries.flow.async_init('test', data={})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    # Discovery flow has been aborted
    assert len(hass.config_entries.flow.async_progress()) == 0


async def test_import_no_confirmation(hass, flow_conf):
    """Test import requires no confirmation to setup."""
    flow = config_entries.HANDLERS['test']()
    flow.hass = hass
    flow_conf['discovered'] = True

    result = await flow.async_step_import(None)
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_import_single_instance(hass, flow_conf):
    """Test import doesn't create second instance."""
    flow = config_entries.HANDLERS['test']()
    flow.hass = hass
    flow_conf['discovered'] = True
    MockConfigEntry(domain='test').add_to_hass(hass)

    result = await flow.async_step_import(None)
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
