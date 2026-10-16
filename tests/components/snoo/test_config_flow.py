"""Test the Happiest Baby Snoo config flow."""

from unittest.mock import AsyncMock

import pytest
from python_snoo.exceptions import InvalidSnooAuth, SnooAuthException

from homeassistant import config_entries
from homeassistant.components.snoo.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import create_entry

from tests.common import MockConfigEntry


async def test_config_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, bypass_api: AsyncMock
) -> None:
    """Test we create the entry successfully."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert result["result"].unique_id == "123e4567-e89b-12d3-a456-426614174000"
    assert len(mock_setup_entry.mock_calls) == 1
    bypass_api.disconnect.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "error_msg"),
    [
        (InvalidSnooAuth, "invalid_auth"),
        (SnooAuthException, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_auth_issues(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    bypass_api: AsyncMock,
    exception,
    error_msg,
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # Set Authorize to fail.
    bypass_api.authorize.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    # Reset auth back to the original
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_msg}
    bypass_api.authorize.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_account_already_configured(
    hass: HomeAssistant, bypass_api: AsyncMock
) -> None:
    """Ensure we abort if the config flow already exists."""
    create_entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth(hass: HomeAssistant, bypass_api: AsyncMock) -> None:
    """Test a successful reauthentication flow."""
    entry = create_entry(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "new-password",
    }
    bypass_api.disconnect.assert_awaited_once()


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("exception", "error_msg"),
    [
        pytest.param(InvalidSnooAuth, "invalid_auth", id="invalid_auth"),
        pytest.param(SnooAuthException, "cannot_connect", id="cannot_connect"),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    bypass_api: AsyncMock,
    exception: type[Exception],
    error_msg: str,
) -> None:
    """Test reauthentication errors and recovery."""
    entry = create_entry(hass)
    result = await entry.start_reauth_flow(hass)

    bypass_api.authorize.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error_msg}

    bypass_api.authorize.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new-password"


@pytest.mark.usefixtures("mock_setup_entry", "bypass_api")
async def test_reauth_unique_id_mismatch(hass: HomeAssistant) -> None:
    """Test reauthentication aborts when the credentials belong to another account."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test-username",
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "sample"},
        unique_id="other-account-uuid",
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.data[CONF_PASSWORD] == "sample"
