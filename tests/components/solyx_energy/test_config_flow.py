"""Tests for the Solyx Energy config flow.

Covers the user setup flow (happy path, validation errors, duplicate device) and
the reauthentication flow (happy path, validation errors). The API client is
mocked at the class level, so no network calls are made.
"""

from typing import TYPE_CHECKING

import pytest

from homeassistant.components.solyx_energy.api import (
    SolyxEnergyAuthError,
    SolyxEnergyDataError,
    SolyxEnergyTokenError,
)
from homeassistant.components.solyx_energy.const import (
    CONF_NYMO_CLIENT_ID,
    CONF_NYMO_CLIENT_SECRET,
    CONF_NYMO_DEVICE_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType

from .const import NYMO_CLIENT_ID, NYMO_CLIENT_SECRET, NYMO_DEVICE_ID

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# Prevent the flow from actually setting up the full integration when an entry is created
pytestmark = pytest.mark.usefixtures("mock_setup_entry")

USER_INPUT = {
    CONF_NYMO_CLIENT_ID: NYMO_CLIENT_ID,
    CONF_NYMO_CLIENT_SECRET: NYMO_CLIENT_SECRET,
    CONF_NYMO_DEVICE_ID: NYMO_DEVICE_ID,
}


@pytest.mark.usefixtures("mock_api_client_class")
async def test_user_flow(hass: HomeAssistant) -> None:
    """The happy path: submit valid credentials and an entry is created."""
    # Start the flow — form should be visible for the user.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Submit the form — the entry should be created with our data.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Nymo {NYMO_DEVICE_ID}"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == NYMO_DEVICE_ID


@pytest.mark.parametrize(
    ("side_effect", "error_key"),
    [
        (SolyxEnergyAuthError, "invalid_auth"),
        (SolyxEnergyTokenError, "data_error"),
        (SolyxEnergyDataError, "data_error"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, mock_api_client_class, side_effect, error_key
) -> None:
    """A failed connection test returns to the form with the right error (see pytest parameters)."""
    mock_api_client_class.async_test_connection.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=USER_INPUT,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error_key}


@pytest.mark.usefixtures("mock_api_client_class")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Setting up the same device twice aborts with 'already_configured'."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=USER_INPUT,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_api_client_class")
async def test_reauth_flow(hass: HomeAssistant, mock_config_entry) -> None:
    """Re-authenticating with valid credentials updates the entry and aborts."""
    mock_config_entry.add_to_hass(hass)

    # Start the reauth flow (as triggered by an auth failure during runtime).
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Submit new credentials; the entry's data should be updated.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NYMO_CLIENT_ID: "new-id",
            CONF_NYMO_CLIENT_SECRET: "new-secret",
        },
    )
    await hass.async_block_till_done()

    # Check if credentials have been updated
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_NYMO_CLIENT_ID] == "new-id"
    assert mock_config_entry.data[CONF_NYMO_CLIENT_SECRET] == "new-secret"
    assert mock_config_entry.data[CONF_NYMO_DEVICE_ID] == NYMO_DEVICE_ID


@pytest.mark.parametrize(
    ("side_effect", "error_key"),
    [
        (SolyxEnergyAuthError, "invalid_auth"),
        (SolyxEnergyTokenError, "data_error"),
        (SolyxEnergyDataError, "data_error"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api_client_class,
    side_effect,
    error_key,
) -> None:
    """A failed connection test during reauth returns to the form with an error (see pytest parameters)."""
    mock_config_entry.add_to_hass(hass)
    mock_api_client_class.async_test_connection.side_effect = side_effect

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NYMO_CLIENT_ID: "new-id",
            CONF_NYMO_CLIENT_SECRET: "new-secret",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error_key}
