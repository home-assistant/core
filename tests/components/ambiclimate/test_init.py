"""Tests for the Ambiclimate integration."""

from unittest.mock import patch

import pytest

from homeassistant.components.ambiclimate import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


@pytest.fixture(name="disable_platforms")
async def disable_platforms_fixture(hass):
    """Disable ambiclimate platforms."""
    with patch("homeassistant.components.ambiclimate.PLATFORMS", []):
        yield


async def test_repair_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    disable_platforms,
) -> None:
    """Test the Ambiclimate configuration entry loading handles the repair."""
    config_entry = MockConfigEntry(
        title="Example 1",
        domain=DOMAIN,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, DOMAIN)

    # Remove the entry
    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Ambiclimate does not implement unload
    assert config_entry.state is ConfigEntryState.FAILED_UNLOAD
    assert issue_registry.async_get_issue(DOMAIN, DOMAIN)
