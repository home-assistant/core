"""Test the Ukraine Alarm integration initialization."""

from unittest.mock import patch

from homeassistant.components.ukraine_alarm.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from . import REGIONS

from tests.common import MockConfigEntry


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

        assert (
            DOMAIN,
            f"deprecated_state_region_{entry.entry_id}",
        ) in issue_registry.issues
