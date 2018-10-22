"""Tests for the Webhook Config Entry Flow helper"""
from unittest.mock import patch, Mock

import pytest
from tests.common import MockConfigEntry

from homeassistant import config_entries, data_entry_flow
from homeassistant.helpers import webhook_config_entry_flow


@pytest.fixture
def flow_conf(hass):
    """Register a handler."""
    with patch.dict(config_entries.HANDLERS):
        webhook_config_entry_flow.register_webhook_flow(
            'test_single', 'Test Single', {}, False)
        webhook_config_entry_flow.register_webhook_flow(
            'test_multiple', 'Test Multiple', {}, True)
        yield {}


async def test_single_entry_allowed(hass, flow_conf):
    """Test only a single entry is allowed."""
    flow = config_entries.HANDLERS['test_single']()
    flow.hass = hass

    MockConfigEntry(domain='test_single').add_to_hass(hass)
    result = await flow.async_step_user()

    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'one_instance_allowed'


async def test_multiple_entries_allowed(hass, flow_conf):
    """Test multiple entries are allowed when specified."""
    flow = config_entries.HANDLERS['test_multiple']()
    flow.hass = hass

    MockConfigEntry(domain='test_multiple').add_to_hass(hass)
    hass.config.api = Mock(base_url='http://example.com')

    result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM


async def test_config_flow_aborts_external_url(hass, flow_conf):
    """Test configuring a webhook without an external url."""
    flow = config_entries.HANDLERS['test_single']()
    flow.hass = hass

    hass.config.api = Mock(base_url='http://192.168.1.10')
    result = await flow.async_step_user()

    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'not_internet_accessible'


async def test_config_flow_registers_webhook(hass, flow_conf):
    """Test setting up an entry creates a webhook."""
    flow = config_entries.HANDLERS['test_single']()
    flow.hass = hass

    hass.config.api = Mock(base_url='http://example.com')
    result = await flow.async_step_user(user_input={})

    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['data']['webhook_id'] is not None
