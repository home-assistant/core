"""Test the London Underground config flow."""

import asyncio
from unittest.mock import patch

import pytest

from homeassistant.components.london_underground.const import (
    CONF_LINE,
    DEFAULT_LINES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


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


async def test_options(hass: HomeAssistant, mock_setup_entry) -> None:
    """Test updating options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_LINE: DEFAULT_LINES},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

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

    with patch(
        "homeassistant.components.london_underground.config_flow.async_get_clientsession"
    ):
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
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "London Underground"
    assert result["data"] == {}
    assert result["options"] == {CONF_LINE: DEFAULT_LINES}


async def test_already_configured(
    hass: HomeAssistant, mock_london_underground_client, mock_setup_entry
) -> None:
    """Try (and fail) setting up a config entry when one already exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_LINE: ["Metropolitan"]},
        title="London Underground",
    )
    # Add and set up the entry
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

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
) -> None:
    """Test a YAML sensor is imported and becomes an operational config entry."""
    # Set up via YAML which will trigger import and set up the config entry
    VALID_CONFIG = {
        "sensor": {"platform": "london_underground", CONF_LINE: ["Metropolitan"]}
    }
    assert await async_setup_component(hass, "sensor", VALID_CONFIG)
    await hass.async_block_till_done()

    # Verify the config entry was created
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    # Verify a warning was issued about YAML deprecation
    assert issue_registry.async_get_issue(DOMAIN, "yaml_deprecated")

    # Check the state after setup completes
    state = hass.states.get("sensor.london_underground_metropolitan")
    assert state
    assert state.state == "Good Service"
    assert state.attributes == {
        "Description": "Nothing to report",
        "attribution": "Powered by TfL Open Data",
        "friendly_name": "London Underground Metropolitan",
        "icon": "mdi:subway",
    }


async def test_failed_yaml_import(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_london_underground_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a YAML sensor is imported and becomes an operational config entry."""
    # Set up via YAML which will trigger import and set up the config entry
    mock_london_underground_client.update.side_effect = asyncio.TimeoutError
    VALID_CONFIG = {
        "sensor": {"platform": "london_underground", CONF_LINE: ["Metropolitan"]}
    }
    assert await async_setup_component(hass, "sensor", VALID_CONFIG)
    await hass.async_block_till_done()

    # Verify the config entry was not created
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 0

    # verify no flows still in progress
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 0

    assert any(
        "Unexpected error trying to connect before importing config" in record.message
        for record in caplog.records
    )
    # Confirm that the import did not happen
    assert not any(
        "Importing London Underground config from configuration.yaml" in record.message
        for record in caplog.records
    )
