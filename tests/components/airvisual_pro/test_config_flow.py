"""Test the AirVisual Pro config flow."""
from unittest.mock import AsyncMock, patch

from pyairvisual.node import (
    InvalidAuthenticationError,
    NodeConnectionError,
    NodeProError,
)
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.airvisual_pro.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.parametrize(
    ("connect_mock", "connect_errors"),
    [
        (AsyncMock(side_effect=Exception), {"base": "unknown"}),
        (AsyncMock(side_effect=InvalidAuthenticationError), {"base": "invalid_auth"}),
        (AsyncMock(side_effect=NodeConnectionError), {"base": "cannot_connect"}),
        (AsyncMock(side_effect=NodeProError), {"base": "unknown"}),
    ],
)
async def test_create_entry(
    hass: HomeAssistant, config, connect_errors, connect_mock, pro, setup_airvisual_pro
) -> None:
    """Test creating an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test errors that can arise when connecting to a Pro:
    with patch.object(pro, "async_connect", connect_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=config
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == connect_errors

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.101"
    assert result["data"] == {
        CONF_IP_ADDRESS: "192.168.1.101",
        CONF_PASSWORD: "password123",
    }


async def test_duplicate_error(
    hass: HomeAssistant, config, config_entry, setup_airvisual_pro
) -> None:
    """Test that errors are shown when duplicates are added."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_step_import(hass: HomeAssistant, config, setup_airvisual_pro) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.101"
    assert result["data"] == {
        CONF_IP_ADDRESS: "192.168.1.101",
        CONF_PASSWORD: "password123",
    }


@pytest.mark.parametrize(
    ("connect_mock", "connect_errors"),
    [
        (AsyncMock(side_effect=Exception), {"base": "unknown"}),
        (AsyncMock(side_effect=InvalidAuthenticationError), {"base": "invalid_auth"}),
        (AsyncMock(side_effect=NodeConnectionError), {"base": "cannot_connect"}),
        (AsyncMock(side_effect=NodeProError), {"base": "unknown"}),
    ],
)
async def test_reauth(
    hass: HomeAssistant,
    config,
    config_entry,
    connect_errors,
    connect_mock,
    pro,
    setup_airvisual_pro,
) -> None:
    """Test re-auth (including errors)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
            "unique_id": config_entry.unique_id,
        },
        data=config,
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Test errors that can arise when connecting to a Pro:
    with patch.object(pro, "async_connect", connect_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "new_password"}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == connect_errors

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "new_password"}
    )

    # Allow reload to finish:
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries()) == 1
