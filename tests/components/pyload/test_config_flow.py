"""Test the pyLoad config flow."""

from unittest.mock import AsyncMock

from pyloadapi.exceptions import CannotConnect, InvalidAuth, ParserError
import pytest

from homeassistant.components.pyload.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import NEW_INPUT, REAUTH_INPUT, USER_INPUT, YAML_INPUT

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_pyloadapi: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (InvalidAuth, "invalid_auth"),
        (CannotConnect, "cannot_connect"),
        (ParserError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_pyloadapi: AsyncMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_pyloadapi.login.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_pyloadapi.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_user_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_pyloadapi: AsyncMock
) -> None:
    """Test we abort user data set when entry is already configured."""

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_import(
    hass: HomeAssistant,
    mock_pyloadapi: AsyncMock,
) -> None:
    """Test that we can import a YAML config."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=YAML_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-name"
    assert result["data"] == USER_INPUT


async def test_flow_import_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_pyloadapi: AsyncMock
) -> None:
    """Test we abort import data set when entry is already configured."""

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=YAML_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (InvalidAuth, "invalid_auth"),
        (CannotConnect, "cannot_connect"),
        (ParserError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
async def test_flow_import_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pyloadapi: AsyncMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test we abort import data set when entry is already configured."""

    mock_pyloadapi.login.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=YAML_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_reauth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pyloadapi: AsyncMock,
) -> None:
    """Test reauth flow."""

    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        REAUTH_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data == NEW_INPUT
    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.parametrize(
    ("side_effect", "error_text"),
    [
        (InvalidAuth, "invalid_auth"),
        (CannotConnect, "cannot_connect"),
        (IndexError, "unknown"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pyloadapi: AsyncMock,
    side_effect: Exception,
    error_text: str,
) -> None:
    """Test reauth flow."""

    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_pyloadapi.login.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        REAUTH_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_text}

    mock_pyloadapi.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        REAUTH_INPUT,
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data == NEW_INPUT
    assert len(hass.config_entries.async_entries()) == 1


async def test_reconfiguration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pyloadapi: AsyncMock,
) -> None:
    """Test reconfiguration flow."""

    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == USER_INPUT
    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.parametrize(
    ("side_effect", "error_text"),
    [
        (InvalidAuth, "invalid_auth"),
        (CannotConnect, "cannot_connect"),
        (IndexError, "unknown"),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pyloadapi: AsyncMock,
    side_effect: Exception,
    error_text: str,
) -> None:
    """Test reconfiguration flow."""

    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_pyloadapi.login.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_text}

    mock_pyloadapi.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == USER_INPUT
    assert len(hass.config_entries.async_entries()) == 1
