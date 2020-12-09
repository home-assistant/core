"""Tests for the LCN config flow."""
from homeassistant import data_entry_flow
from homeassistant.components.lcn import config_flow
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.async_mock import patch
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
        data = {CONF_HOST: "pchk", CONF_USERNAME: "lcn", CONF_PASSWORD: "lcn"}
        result = await flow.async_step_import(data)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "pchk"
        assert result["data"] == {CONF_USERNAME: "lcn", CONF_PASSWORD: "lcn"}


async def test_step_import_existing_host(hass):
    """Test that the import step works."""
    flow = init_config_flow(hass)

    with patch(
        "homeassistant.config_entries.ConfigFlow.async_set_unique_id",
        return_value=MockConfigEntry(),
    ):
        data = {"host": "pchk"}
        result = await flow.async_step_import(data)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
