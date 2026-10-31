"""Tests for the Solyx Energy config flow.

Covers the user setup flow (happy path, validation errors, duplicate account).
The API client is mocked at the class level, so no network calls are made.
"""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from solyx_energy_api.exceptions import (
    SolyxEnergyAuthError,
    SolyxEnergyDataError,
    SolyxEnergyTokenError,
)

from homeassistant.components.solyx_energy_cloud.const import (
    CONF_NYMO_CLIENT_ID,
    CONF_NYMO_CLIENT_SECRET,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType

from .const import NYMO_CLIENT_ID, NYMO_CLIENT_SECRET

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# Prevent the flow from actually setting up the full integration when an entry is created
pytestmark = pytest.mark.usefixtures("mock_setup_entry")

USER_INPUT = {
    CONF_NYMO_CLIENT_ID: NYMO_CLIENT_ID,
    CONF_NYMO_CLIENT_SECRET: NYMO_CLIENT_SECRET,
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
    assert result["title"] == "Solyx Energy Cloud"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == NYMO_CLIENT_ID


@pytest.mark.parametrize(
    ("side_effect", "error_key"),
    [
        pytest.param(SolyxEnergyAuthError(), "invalid_auth", id="auth_error"),
        pytest.param(SolyxEnergyTokenError(), "cannot_connect", id="token_error"),
        pytest.param(SolyxEnergyDataError(), "cannot_connect", id="data_error"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_api_client_class: AsyncMock,
    side_effect: Exception,
    error_key: str,
) -> None:
    """A failed connection test shows the right error; fixing it finishes the flow."""
    mock_api_client_class.async_test_connection.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error_key}

    mock_api_client_class.async_test_connection.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Solyx Energy Cloud"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == NYMO_CLIENT_ID


@pytest.mark.usefixtures("mock_api_client_class")
async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Setting up the same account twice aborts with 'already_configured'."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
