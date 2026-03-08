"""The tests for the london_underground platform."""

import asyncio

import pytest

from homeassistant.components.london_underground.const import CONF_LINE, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

VALID_CONFIG = {
    "sensor": {"platform": "london_underground", CONF_LINE: ["Metropolitan"]}
}


async def test_valid_state(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_london_underground_client,
    mock_config_entry,
) -> None:
    """Test operational London Underground sensor using a mock config entry."""
    # Ensure the entry is fully loaded
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Confirm that the expected entity exists and is correct
    state = hass.states.get("sensor.london_underground_metropolitan")
    assert state is not None
    assert state.state == "Good Service"
    assert state.attributes == {
        "Description": "Nothing to report",
        "attribution": "Powered by TfL Open Data",
        "friendly_name": "London Underground Metropolitan",
        "icon": "mdi:subway",
    }

    # No YAML warning should be issued, since setup was not via YAML
    assert not issue_registry.async_get_issue(DOMAIN, "yaml_deprecated")


async def test_yaml_import(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_london_underground_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a YAML sensor is imported and becomes an operational config entry."""
    # Set up via YAML which will trigger import and set up the config entry
    VALID_CONFIG = {
        "sensor": {
            "platform": "london_underground",
            CONF_LINE: ["Metropolitan", "London Overground"],
        }
    }
    assert await async_setup_component(hass, "sensor", VALID_CONFIG)
    await hass.async_block_till_done()

    # Verify the config entry was created
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    # Verify a warning was issued about YAML deprecation
    assert issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, "deprecated_yaml")

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

    # Since being renamed London overground is no longer returned by the API
    # So check that we do not import it and that we warn the user
    state = hass.states.get("sensor.london_underground_london_overground")
    assert not state
    assert any(
        "London Overground was removed from the configuration as the line has been divided and renamed"
        in record.message
        for record in caplog.records
    )


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

    assert not any(
        "migrated to a config entry and can be safely removed" in record.message
        for record in caplog.records
    )

    # Verify a warning was issued about YAML not being imported
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
