"""Test the OpenWeatherMap integration setup."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.openweathermap.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir


@pytest.mark.parametrize("mode", ["v2.5"], indirect=True)
@pytest.mark.usefixtures("owm_client_mock")
async def test_deprecated_v25_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the V2.5 deprecation issue is linked to its config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    issue_id = f"deprecated_v25_{mock_config_entry.entry_id}"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.config_entry_id == mock_config_entry.entry_id

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
