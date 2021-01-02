"""Tests for the LCN config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.lcn import config_flow
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS, CONF_PORT

from tests.common import MockConfigEntry


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.LcnFlowHandler()
    flow.hass = hass
    flow.context = {"source": SOURCE_IMPORT}
    return flow


async def test_step_import(hass):
    """Test that the import step works."""
    flow = init_config_flow(hass)

    with patch(
        "homeassistant.components.lcn.async_setup_entry", return_value=True
    ), patch("homeassistant.components.lcn.async_setup", return_value=True):
        data = {CONF_IP_ADDRESS: "127.0.0.1", CONF_PORT: 4114, CONF_HOST: "pchk"}
        result = await flow.async_step_import(data)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "pchk"
        assert result["data"] == {CONF_IP_ADDRESS: "127.0.0.1", CONF_PORT: 4114}


async def test_step_import_existing_host(hass):
    """Test that the import step works."""
    flow = init_config_flow(hass)

    mock_entry = MockConfigEntry()
    with patch(
        "homeassistant.components.lcn.config_flow.get_config_entry",
        return_value=mock_entry,
    ):
        data = {
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_PORT: 4114,
            CONF_HOST: "pchk",
        }
        result = await flow.async_step_import(data)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "existing_configuration_updated"
        assert mock_entry.source == SOURCE_IMPORT
        assert mock_entry.data == {CONF_IP_ADDRESS: "127.0.0.1", CONF_PORT: 4114}
