"""Tests for HomematicIP Cloud config flow."""
from homeassistant.components import homematicip_cloud as hmipc
from homeassistant.components.homematicip_cloud import config_flow

from tests.common import MockConfigEntry


async def test_import_config(hass):
    """Test importing a host with an existing config file."""
    flow = config_flow.HomematicipCloudFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import({
        hmipc.HMIPC_HAPID: 'ABC123',
        hmipc.HMIPC_AUTHTOKEN: '123',
        hmipc.HMIPC_NAME: 'hmip'
    })

    assert result['type'] == 'create_entry'
    assert result['title'] == 'ABC123'
    assert result['data'] == {
        hmipc.HMIPC_HAPID: 'ABC123',
        hmipc.HMIPC_AUTHTOKEN: '123',
        hmipc.HMIPC_NAME: 'hmip'
    }


async def test_import_existing_config(hass):
    """Test importing a host with an existing config file."""
    flow = config_flow.HomematicipCloudFlowHandler()
    flow.hass = hass

    MockConfigEntry(domain=hmipc.DOMAIN, data={
        hmipc.HMIPC_HAPID: 'ABC123',
    }).add_to_hass(hass)

    result = await flow.async_step_import({
        hmipc.HMIPC_HAPID: 'ABC123',
        hmipc.HMIPC_AUTHTOKEN: '123',
        hmipc.HMIPC_NAME: 'hmip'
    })

    assert result['type'] == 'abort'
