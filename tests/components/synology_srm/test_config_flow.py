"""Test Synology SRM configuration."""

from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import ConnectionError
from synology_srm.http import SynologyApiError, SynologyHttpException

from homeassistant.components.synology_srm.const import CONF_TRACKED_DEVICES, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import CLIENT, CONFIG, MAC


async def test_user_flow(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test setup with defaults and duplicate prevention."""
    with patch(
        "homeassistant.components.synology_srm.async_setup_entry", return_value=None
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "host": CONFIG["host"],
                "username": "admin",
                "password": "password",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "devices"
        assert result["data_schema"]({}) == {CONF_TRACKED_DEVICES: []}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TRACKED_DEVICES: []}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "no_devices_selected"}
        assert not hass.config_entries.async_entries(DOMAIN)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TRACKED_DEVICES: [MAC]}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {**CONFIG, CONF_TRACKED_DEVICES: [MAC]}
        assert result["title"] == CONFIG["host"]
        mock_client.http.disable_https_verify.assert_called_once()
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONFIG
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(ConnectionError(), "cannot_connect", id="connection"),
        pytest.param(SynologyHttpException(), "cannot_connect", id="http"),
        pytest.param(SynologyApiError(400, "Invalid login"), "invalid_auth", id="auth"),
        pytest.param(SynologyApiError(500, "API failure"), "cannot_connect", id="api"),
        pytest.param(RuntimeError(), "unknown", id="unexpected"),
    ],
)
async def test_errors(
    hass: HomeAssistant,
    mock_client: MagicMock,
    error: Exception,
    expected: str,
) -> None:
    """Test errors and recovery in the same flow."""
    mock_client.core.get_network_nsm_device.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )
    assert result["errors"] == {"base": expected}
    mock_client.core.get_network_nsm_device.side_effect = None
    with patch(
        "homeassistant.components.synology_srm.async_setup_entry", return_value=None
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONFIG
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "devices"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TRACKED_DEVICES: [MAC]}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_verify_ssl(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test certificate verification stays enabled when requested."""
    with patch(
        "homeassistant.components.synology_srm.async_setup_entry", return_value=None
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={**CONFIG, "verify_ssl": True}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "devices"
    mock_client.http.disable_https_verify.assert_not_called()


async def test_no_devices(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Allow retrying when the router has no known devices."""
    mock_client.core.get_network_nsm_device.return_value = []
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_devices_found"}
    assert not hass.config_entries.async_entries(DOMAIN)
    mock_client.core.get_network_nsm_device.return_value = [CLIENT]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )
    assert result["step_id"] == "devices"
    with patch(
        "homeassistant.components.synology_srm.async_setup_entry", return_value=None
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TRACKED_DEVICES: [MAC]}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
