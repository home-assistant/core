"""Test the Zinvolt config flow."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from zinvolt.exceptions import ZinvoltAuthenticationError, ZinvoltError

from homeassistant.components.zinvolt.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import TOKEN


@pytest.mark.usefixtures("mock_zinvolt_client")
async def test_full_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test the full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@test.com",
            CONF_PASSWORD: "yes",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@test.com"
    assert result["data"] == {CONF_ACCESS_TOKEN: TOKEN}
    assert result["result"].unique_id == "a0226b8f-98fe-4524-b369-272b466b8797"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("method", "exception", "error"),
    [
        pytest.param(
            "login", ZinvoltAuthenticationError, "invalid_auth", id="invalid_auth"
        ),
        pytest.param("login", ZinvoltError, "cannot_connect", id="cannot_connect"),
        pytest.param("login", Exception, "unknown", id="unknown"),
        pytest.param("get_user_id", ZinvoltError, "cannot_connect", id="invalid_token"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_zinvolt_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    method: str,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    getattr(mock_zinvolt_client, method).side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@test.com",
            CONF_PASSWORD: "yes",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    getattr(mock_zinvolt_client, method).side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@test.com",
            CONF_PASSWORD: "yes",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_zinvolt_client")
async def test_duplicate_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we handle duplicate entries."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@test.com",
            CONF_PASSWORD: "yes",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_zinvolt_client", "mock_setup_entry")
async def test_reauth_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the reauthentication flow."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={CONF_ACCESS_TOKEN: "old_token"}
    )

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@test.com",
            CONF_PASSWORD: "new_password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {CONF_ACCESS_TOKEN: TOKEN}


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ZinvoltAuthenticationError, "invalid_auth"),
        (ZinvoltError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_zinvolt_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: type[Exception],
    error: str,
) -> None:
    """Test the reauthentication flow recovers from errors."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_zinvolt_client.login.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@test.com",
            CONF_PASSWORD: "new_password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_zinvolt_client.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@test.com",
            CONF_PASSWORD: "new_password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("mock_zinvolt_client", "mock_setup_entry")
async def test_reauth_flow_unique_id_mismatch(hass: HomeAssistant) -> None:
    """Test the reauthentication flow aborts when logging in to another account."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="other@test.com",
        unique_id="other-user-id",
        data={CONF_ACCESS_TOKEN: "old_token"},
    )
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@test.com",
            CONF_PASSWORD: "yes",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data == {CONF_ACCESS_TOKEN: "old_token"}


@pytest.mark.usefixtures("mock_zinvolt_client", "mock_setup_entry")
async def test_reconfigure_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the reconfigure flow."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, title="old@test.com", data={CONF_ACCESS_TOKEN: "old_token"}
    )

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@test.com",
            CONF_PASSWORD: "new_password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.title == "test@test.com"
    assert mock_config_entry.data == {CONF_ACCESS_TOKEN: TOKEN}


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ZinvoltAuthenticationError, "invalid_auth"),
        (ZinvoltError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_zinvolt_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: type[Exception],
    error: str,
) -> None:
    """Test the reconfigure flow recovers from errors."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    mock_zinvolt_client.login.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@test.com",
            CONF_PASSWORD: "new_password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": error}

    mock_zinvolt_client.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@test.com",
            CONF_PASSWORD: "new_password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("mock_zinvolt_client", "mock_setup_entry")
async def test_reconfigure_flow_unique_id_mismatch(hass: HomeAssistant) -> None:
    """Test the reconfigure flow aborts when logging in to another account."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="other@test.com",
        unique_id="other-user-id",
        data={CONF_ACCESS_TOKEN: "old_token"},
    )
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@test.com",
            CONF_PASSWORD: "yes",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.title == "other@test.com"
    assert mock_config_entry.data == {CONF_ACCESS_TOKEN: "old_token"}
