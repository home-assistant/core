"""Tests for the Atomberg config flow."""

from unittest.mock import AsyncMock

from atomberg_api import AtombergAuthError, AtombergConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.atomberg.const import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import API_KEY, REFRESH_TOKEN

USER_INPUT = {CONF_API_KEY: API_KEY, CONF_REFRESH_TOKEN: REFRESH_TOKEN}


@pytest.mark.usefixtures("mock_client", "mock_setup_entry")
async def test_full_flow(hass: HomeAssistant) -> None:
    """Test the user flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Atomberg"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == API_KEY


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (AtombergAuthError, "invalid_auth"),
        (AtombergConnectionError, "cannot_connect"),
        (RuntimeError, "unknown"),
    ],
)
async def test_flow_errors_then_recovery(
    hass: HomeAssistant, mock_client: AsyncMock, exception: type[Exception], error: str
) -> None:
    """Test errors are shown and the flow can then succeed."""
    mock_client.async_get_devices.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_client.async_get_devices.side_effect = None
    mock_client.async_get_devices.return_value = []
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_client", "mock_setup_entry")
async def test_duplicate_account(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the same API key cannot be added twice."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_client", "mock_setup_entry")
async def test_reauth(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test reauthentication updates the refresh token."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY, CONF_REFRESH_TOKEN: "new-token"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_REFRESH_TOKEN] == "new-token"


@pytest.mark.usefixtures("mock_client", "mock_setup_entry")
async def test_reauth_wrong_account(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauthentication with another account's key aborts."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "other-key", CONF_REFRESH_TOKEN: "other-token"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
