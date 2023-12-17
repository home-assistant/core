"""Tests for Glances integration."""
from unittest.mock import MagicMock

from glances_api.exceptions import (
    GlancesApiAuthorizationError,
    GlancesApiConnectionError,
)
import pytest

from homeassistant.components.glances.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_get as async_get_issue_registry,
)

from . import MOCK_USER_INPUT

from tests.common import MockConfigEntry


async def test_successful_config_entry(hass: HomeAssistant) -> None:
    """Test that Glances is configu red successfully."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state == ConfigEntryState.LOADED


async def test_entry_deprecated_version(hass: HomeAssistant) -> None:
    """Test creating an issue if glances server is version 2."""
    registry = async_get_issue_registry(hass)
    issue = registry.async_get_issue(DOMAIN, "deprecated_version")
    assert issue is None

    v2_config_entry = MOCK_USER_INPUT.copy()
    v2_config_entry["version"] = 2

    entry = MockConfigEntry(domain=DOMAIN, data=v2_config_entry)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state == ConfigEntryState.LOADED

    issue = registry.async_get_issue(DOMAIN, "deprecated_version")
    assert issue is not None
    assert issue.severity == IssueSeverity.WARNING


@pytest.mark.parametrize(
    ("error", "entry_state"),
    [
        (GlancesApiAuthorizationError, ConfigEntryState.SETUP_ERROR),
        (GlancesApiConnectionError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_error(
    hass: HomeAssistant,
    error: Exception,
    entry_state: ConfigEntryState,
    mock_api: MagicMock,
) -> None:
    """Test Glances failed due to api error."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    mock_api.return_value.get_ha_sensor_data.side_effect = error
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is entry_state


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test removing Glances."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data
