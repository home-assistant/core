"""Test the Ukraine Alarm integration initialization."""

from unittest.mock import patch

import aiohttp
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ukraine_alarm.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from . import REGIONS


async def test_migration_v1_to_v2_state_without_districts(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test migration allows states without districts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={"region": "1", "name": "State 1"},
        unique_id="1",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.ukraine_alarm.Client.get_regions",
            return_value=REGIONS,
        ),
        patch(
            "homeassistant.components.ukraine_alarm.Client.get_alerts",
            return_value=[{"activeAlerts": []}],
        ),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)
        assert result is True
        assert entry.version == 2

        assert (
            DOMAIN,
            f"deprecated_state_region_{entry.entry_id}",
        ) not in issue_registry.issues


async def test_migration_v1_to_v2_state_with_districts_fails(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test migration rejects states with districts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={"region": "2", "name": "State 2"},
        unique_id="2",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ukraine_alarm.Client.get_regions",
        return_value=REGIONS,
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)
        assert result is False

        issue_id = f"deprecated_state_region_{entry.entry_id}"
        issue = issue_registry.async_get_issue(DOMAIN, issue_id)
        assert issue is not None
        assert issue.config_entry_id == entry.entry_id

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert entry.reason == (
        "The region State 2 is a state-level region, which is no longer supported."
        " Remove this integration entry and add it again, selecting a district or"
        " community"
    )

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_migration_v1_to_v2_cannot_connect(hass: HomeAssistant) -> None:
    """Test migration is retried when the regions cannot be fetched."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={"region": "1", "name": "State 1"},
        unique_id="1",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ukraine_alarm.Client.get_regions",
        side_effect=aiohttp.ClientError,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.reason == "Failed to fetch the regions from the Ukraine Alarm API"
    assert entry.version == 1
