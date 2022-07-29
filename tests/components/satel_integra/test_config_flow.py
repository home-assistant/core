"""Test config flow."""

from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.satel_integra.const import DEFAULT_PORT, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

DEFAULT_VALUES = {CONF_PORT: DEFAULT_PORT}


async def test_user(hass):
    """Test we can start a config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]


async def test_user_confirm(hass: HomeAssistant):
    """Test we can finish a config flow."""

    mockdata = {CONF_HOST: "192.168.1.1"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "satel_integra.satel_integra.AsyncSatel.connect", return_value=True
    ) as mock_connection, patch(
        "homeassistant.components.satel_integra.async_setup_entry", return_value=True
    ) as mock_setup_entry:

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], mockdata
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == mockdata[CONF_HOST]
    assert result2["data"] == {**DEFAULT_VALUES, **mockdata}

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_connection.mock_calls) == 1


async def test_user_confirm_failed(hass):
    """Test we can finish a config flow."""

    mockdata = {CONF_HOST: "192.168.1.1"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "satel_integra.satel_integra.AsyncSatel.connect", return_value=False
    ) as mock_connection:

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], mockdata
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"]["base"] == "cannot_connect"

    assert len(mock_connection.mock_calls) == 1
