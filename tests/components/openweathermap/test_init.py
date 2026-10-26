"""Test the OpenWeatherMap integration setup."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.openweathermap.const import (
    DEFAULT_OWM_MODE,
    DOMAIN,
    OWM_MODE_V30,
)
from homeassistant.const import CONF_MODE
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


@pytest.mark.parametrize("version", [1, 2, 3, 4])
@pytest.mark.parametrize("mode", ["v2.5", "current", OWM_MODE_V30], indirect=True)
@pytest.mark.usefixtures("owm_client_mock")
async def test_migration_preserves_v30_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    version: int,
) -> None:
    """Legacy entries still migrate to One Call 3.0."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry.data,
        options=mock_config_entry.options,
        version=version,
        unique_id=mock_config_entry.unique_id,
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.version == 5
    assert mock_config_entry.options[CONF_MODE] == OWM_MODE_V30 == DEFAULT_OWM_MODE
