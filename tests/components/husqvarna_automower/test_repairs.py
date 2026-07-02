"""Test repairs for Husqvarna Automower."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.components.husqvarna_automower.coordinator import SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import slugify

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_invalid_mower_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an issue is created for an invalid mower."""
    mower_name = "Garden mower"
    issue_id = f"invalid_mower_{slugify(mower_name)}"
    mock_automower_client.invalid_mowers = {mower_name}

    await setup_integration(hass, mock_config_entry)

    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.is_fixable is False
    assert issue.translation_key == "invalid_mower"
    assert issue.translation_placeholders == {
        "mower_name": mower_name,
    }

    # Simulate reloading home assistant by reloading the integration
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.is_fixable is False
    assert issue.translation_key == "invalid_mower"
    assert issue.translation_placeholders == {
        "mower_name": mower_name,
    }

    # Simulate mower behaving properly during runtime
    mock_automower_client.invalid_mowers.clear()
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is None
