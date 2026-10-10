"""Tests for the xiaomi config flow."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant.components.xiaomi.const import DOMAIN
from homeassistant.components.xiaomi.router import (
    XiaomiAuthError,
    XiaomiConnectionError,
    XiaomiTimeoutError,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

REAUTH_INPUT = {
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "new-password",
}

USER_INPUT = {
    CONF_HOST: "192.168.31.1",
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "password",
}

# Login failures raised by the client, mapped to the error the flow
# should report.
LOGIN_ERRORS: list[tuple[dict[str, Any], str]] = [
    ({"side_effect": XiaomiConnectionError()}, "cannot_connect"),
    ({"side_effect": XiaomiTimeoutError()}, "cannot_connect"),
    ({"side_effect": XiaomiAuthError()}, "invalid_auth"),
]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow(hass: HomeAssistant, mock_xiaomi_client: MagicMock) -> None:
    """Test the happy path of the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.31.1"
    assert result["data"] == USER_INPUT


@pytest.mark.usefixtures("mock_setup_entry", "mock_xiaomi_client")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the user flow aborts when the host is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("login_config", "base_error"),
    LOGIN_ERRORS,
    ids=["connection_error", "timeout", "invalid_auth"],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_xiaomi_client: MagicMock,
    login_config: dict[str, Any],
    base_error: str,
) -> None:
    """Test the user flow shows errors and recovers on retry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    mock_xiaomi_client.login.configure_mock(**login_config)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": base_error}

    mock_xiaomi_client.login.configure_mock(side_effect=None, return_value=None)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_flow(hass: HomeAssistant, mock_xiaomi_client: MagicMock) -> None:
    """Test the happy path of the import flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.31.1"
    assert result["data"] == USER_INPUT


@pytest.mark.usefixtures("mock_setup_entry", "mock_xiaomi_client")
async def test_import_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the import flow aborts when the host is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("login_config", "reason"),
    LOGIN_ERRORS,
    ids=["connection_error", "timeout", "invalid_auth"],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_flow_errors(
    hass: HomeAssistant,
    mock_xiaomi_client: MagicMock,
    login_config: dict[str, Any],
    reason: str,
) -> None:
    """Test the import flow aborts when connecting fails."""
    mock_xiaomi_client.login.configure_mock(**login_config)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_xiaomi_client: MagicMock,
) -> None:
    """Test the happy path of the reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {
        "host": mock_config_entry.data[CONF_HOST],
        "name": mock_config_entry.title,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=REAUTH_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"


@pytest.mark.parametrize(
    ("login_config", "base_error"),
    LOGIN_ERRORS,
    ids=["connection_error", "timeout", "invalid_auth"],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_xiaomi_client: MagicMock,
    login_config: dict[str, Any],
    base_error: str,
) -> None:
    """Test the reauth flow shows errors and recovers on retry."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM

    mock_xiaomi_client.login.configure_mock(**login_config)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=REAUTH_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": base_error}
    assert result["description_placeholders"] == {
        "host": mock_config_entry.data[CONF_HOST],
        "name": mock_config_entry.title,
    }

    mock_xiaomi_client.login.configure_mock(side_effect=None, return_value=None)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=REAUTH_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"
