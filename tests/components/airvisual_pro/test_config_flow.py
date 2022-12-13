"""Test the AirVisual Pro config flow."""
from unittest.mock import patch

from pyairvisual.node import NodeProError
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.airvisual_pro.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD


async def test_duplicate_error(hass, config, config_entry):
    """Test that errors are shown when duplicates are added."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "exc,errors",
    [
        (NodeProError, {"base": "cannot_connect"}),
        (Exception, {"base": "unknown"}),
    ],
)
async def test_errors(hass, config, exc, errors, setup_airvisual_pro):
    """Test that an exceptions show an error."""
    with patch(
        "homeassistant.components.airvisual_pro.config_flow.NodeSamba.async_connect",
        side_effect=exc,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=config
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == errors

    # Validate that we can still proceed after an error if the underlying condition
    # resolves:
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.101"
    assert result["data"] == {
        CONF_IP_ADDRESS: "192.168.1.101",
        CONF_PASSWORD: "password123",
    }


async def test_step_user(hass, config, setup_airvisual_pro):
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.101"
    assert result["data"] == {
        CONF_IP_ADDRESS: "192.168.1.101",
        CONF_PASSWORD: "password123",
    }
