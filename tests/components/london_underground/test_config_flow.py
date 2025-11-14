"""Test the London Underground config flow."""

import asyncio

import pytest

from homeassistant.components.london_underground.const import (
    CONF_LINE,
    DEFAULT_LINES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir


async def test_validate_input_success(
    hass: HomeAssistant, mock_setup_entry, mock_london_underground_client
) -> None:
    """Test successful validation of TfL API."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LINE: ["Bakerloo", "Central"]},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "London Underground"
    assert result["data"] == {}
    assert result["options"] == {CONF_LINE: ["Bakerloo", "Central"]}


async def test_options(
    hass: HomeAssistant, mock_setup_entry, mock_config_entry
) -> None:
    """Test updating options."""
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_LINE: ["Bakerloo", "Central"],
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_LINE: ["Bakerloo", "Central"],
    }


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (Exception, "cannot_connect"),
        (asyncio.TimeoutError, "timeout_connect"),
    ],
)
async def test_validate_input_exceptions(
    hass: HomeAssistant,
    mock_setup_entry,
    mock_london_underground_client,
    side_effect,
    expected_error,
) -> None:
    """Test validation with connection and timeout errors."""

    mock_london_underground_client.update.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LINE: ["Bakerloo", "Central"]},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    # confirm recovery after error
    mock_london_underground_client.update.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "London Underground"
    assert result["data"] == {}
    assert result["options"] == {CONF_LINE: DEFAULT_LINES}


async def test_already_configured(
    hass: HomeAssistant,
    mock_london_underground_client,
    mock_setup_entry,
    mock_config_entry,
) -> None:
    """Try (and fail) setting up a config entry when one already exists."""

    # Try to start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_yaml_import(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_london_underground_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a YAML sensor is imported and becomes an operational config entry."""
    # Set up via YAML which will trigger import and set up the config entry
    IMPORT_DATA = {
        "platform": "london_underground",
        "line": ["Central", "Piccadilly", "Victoria", "Bakerloo", "Northern"],
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=IMPORT_DATA
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "London Underground"
    assert result["data"] == {}
    assert result["options"] == {
        CONF_LINE: ["Central", "Piccadilly", "Victoria", "Bakerloo", "Northern"]
    }


async def test_failed_yaml_import_connection(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_london_underground_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a YAML sensor is imported and becomes an operational config entry."""
    # Set up via YAML which will trigger import and set up the config entry
    mock_london_underground_client.update.side_effect = asyncio.TimeoutError
    IMPORT_DATA = {
        "platform": "london_underground",
        "line": ["Central", "Piccadilly", "Victoria", "Bakerloo", "Northern"],
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=IMPORT_DATA
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_failed_yaml_import_already_configured(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_london_underground_client,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry,
) -> None:
    """Test a YAML sensor is imported and becomes an operational config entry."""
    # Set up via YAML which will trigger import and set up the config entry

    IMPORT_DATA = {
        "platform": "london_underground",
        "line": ["Central", "Piccadilly", "Victoria", "Bakerloo", "Northern"],
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=IMPORT_DATA
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
