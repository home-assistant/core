"""Tests for the Netio config flow."""

from unittest.mock import MagicMock

from Netio.exceptions import AuthError, CommunicationError
import pytest
import requests

from homeassistant.components.netio.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_HOST: "192.168.1.10",
    CONF_PORT: 80,
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "netio-password",
    CONF_SSL: False,
    CONF_VERIFY_SSL: True,
}


@pytest.mark.usefixtures("mock_netio", "mock_setup_entry")
async def test_full_flow(hass: HomeAssistant) -> None:
    """Test the full happy path of the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "PowerCable"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == "24A42C39F87E"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(AuthError("invalid"), "invalid_auth", id="invalid_auth"),
        pytest.param(
            CommunicationError("failed"), "cannot_connect", id="cannot_connect"
        ),
        pytest.param(
            requests.exceptions.ConnectionError(),
            "cannot_connect",
            id="connection_error",
        ),
        pytest.param(ValueError("bogus"), "unknown", id="unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_errors(
    hass: HomeAssistant,
    mock_netio: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test error handling and recovery in the user flow."""
    mock_netio.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_netio.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_netio", "mock_setup_entry")
async def test_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test aborting if the device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
