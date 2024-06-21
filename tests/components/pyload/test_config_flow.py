"""Test the pyLoad config flow."""

from typing import Any
from unittest.mock import AsyncMock

from pyloadapi.exceptions import CannotConnect, InvalidAuth, ParserError
import pytest

from homeassistant.components.pyload.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.issue_registry as ir

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_pyloadapi")
async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    userinput: dict[str, Any],
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        userinput,
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == userinput[CONF_NAME]
    assert result["data"] == userinput
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
    userinput: dict[str, Any],
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
        userinput,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_pyloadapi.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        userinput,
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == userinput[CONF_NAME]
    assert result["data"] == userinput
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_pyloadapi")
async def test_flow_user_init_data_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    userinput: dict[str, Any],
) -> None:
    """Test we abort user data set when entry is already configured."""

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=userinput,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_pyloadapi")
async def test_flow_import(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, userinput: dict[str, Any]
) -> None:
    """Test that we can import a YAML config."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=userinput,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == userinput[CONF_NAME]
    assert result["data"] == userinput

    assert issue_registry.async_get_issue(
        domain=HOMEASSISTANT_DOMAIN,
        issue_id=f"deprecated_yaml_{DOMAIN}",
    )


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (CannotConnect(), "cannot_connect"),
        (InvalidAuth(), "invalid_auth"),
        (ParserError(), "cannot_connect"),
        (IndexError(), "unknown"),
    ],
)
async def test_flow_import_error(
    hass: HomeAssistant,
    mock_pyloadapi: AsyncMock,
    raise_error,
    text_error,
    userinput: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that we can import a YAML config."""

    mock_pyloadapi.login.side_effect = raise_error
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=userinput,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    assert issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id=f"deprecated_yaml_import_issue_{text_error}",
    )
