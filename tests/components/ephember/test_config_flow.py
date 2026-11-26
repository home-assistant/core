"""Tests for the EPH Controls Ember config flow."""

from unittest.mock import MagicMock

from pyephember2.pyephember2 import EphEmberError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ephember.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_PASSWORD, MOCK_USER_ID, MOCK_USERNAME

USER_INPUT = {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow(hass: HomeAssistant, mock_ember: MagicMock) -> None:
    """Test setting up an account from the UI."""
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
    assert result["title"] == MOCK_USERNAME
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == MOCK_USER_ID


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (EphEmberError("Cannot connect to Ember"), "cannot_connect"),
        (RuntimeError("Unable to login."), "invalid_auth"),
        (ValueError("Unexpected"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_ember: MagicMock,
    error: Exception,
    message: str,
) -> None:
    """Test errors are shown and the user can try again."""
    mock_ember.messenging_credentials.side_effect = error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": message}

    mock_ember.messenging_credentials.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_ember")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the same account cannot be added twice."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry", "mock_ember")
async def test_import_flow(hass: HomeAssistant) -> None:
    """Test importing the YAML configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USERNAME
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == MOCK_USER_ID


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (EphEmberError("Cannot connect to Ember"), "cannot_connect"),
        (RuntimeError("Unable to login."), "invalid_auth"),
        (ValueError("Unexpected"), "unknown"),
    ],
)
async def test_import_flow_errors(
    hass: HomeAssistant, mock_ember: MagicMock, error: Exception, reason: str
) -> None:
    """Test the import aborts when the account cannot be checked."""
    mock_ember.messenging_credentials.side_effect = error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_ember: MagicMock
) -> None:
    """Test entering a new password after it was rejected."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"]["username"] == MOCK_USERNAME

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_USERNAME: MOCK_USERNAME,
        CONF_PASSWORD: "new-password",
    }


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (EphEmberError("Cannot connect to Ember"), "cannot_connect"),
        (RuntimeError("Unable to login."), "invalid_auth"),
        (ValueError("Unexpected"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ember: MagicMock,
    error: Exception,
    message: str,
) -> None:
    """Test errors are shown and the user can try again."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    mock_ember.messenging_credentials.side_effect = error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": message}

    mock_ember.messenging_credentials.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_other_account(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_ember: MagicMock
) -> None:
    """Test a password for a different EPH Ember account is refused."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    mock_ember.messenging_credentials.return_value = {
        "user_id": "99999",
        "token": "token",
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data[CONF_PASSWORD] == MOCK_PASSWORD
