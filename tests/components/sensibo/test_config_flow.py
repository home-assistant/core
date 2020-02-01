"""Test the Sensibo config flow."""
from unittest.mock import patch

from pysensibo import SensiboError

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.sensibo import ALL
from homeassistant.components.sensibo.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_ID

from tests.common import mock_coro

MOCK_CONFIG_BASIC = {DOMAIN: [{CONF_API_KEY: "config-fake-api-key"}]}


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "pysensibo.SensiboClient.async_get_devices", return_value=mock_coro({})
    ), patch(
        "homeassistant.components.sensibo.async_setup", return_value=mock_coro(True)
    ) as mock_setup, patch(
        "homeassistant.components.sensibo.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "test-api-key"},
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Sensibo AC"
    assert result2["data"] == {CONF_API_KEY: "test-api-key", CONF_ID: ALL}

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_connection_error(hass):
    """Test that a connection error is handled by the flow."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "pysensibo.SensiboClient.async_get_devices",
        return_value=mock_coro(None, SensiboError),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "test-api-key"},
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "connection_error"}
