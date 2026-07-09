"""Tests for the Aruba ClearPass (cppm_tracker) device tracker."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
import requests

from homeassistant.components.cppm_tracker.const import DOMAIN
from homeassistant.components.cppm_tracker.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_API_KEY,
    CONF_CLIENT_ID,
    CONF_HOST,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import MAC_LAPTOP, MAC_OFFLINE, MAC_PHONE, MOCK_CONFIG, MOCK_HOST

from tests.common import MockConfigEntry, async_fire_time_changed

YAML_CONFIG = {
    "device_tracker": [
        {
            "platform": DOMAIN,
            CONF_HOST: MOCK_HOST,
            CONF_CLIENT_ID: "client",
            CONF_API_KEY: "secret",
        }
    ]
}


async def test_only_online_endpoints_are_tracked(
    hass: HomeAssistant,
    mock_clearpass: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that only endpoints reported online become tracked entities."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert {e.unique_id for e in entries} == {MAC_PHONE, MAC_LAPTOP}
    assert MAC_OFFLINE not in {e.unique_id for e in entries}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_marked_away_when_offline(
    hass: HomeAssistant,
    mock_clearpass: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a tracked device flips to away once ClearPass reports it offline."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id("device_tracker", DOMAIN, MAC_PHONE)
    assert hass.states.get(entity_id).state == STATE_HOME

    mock_clearpass.return_value.online_status.side_effect = lambda mac: False
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_NOT_HOME


async def test_setup_scanner_imports_yaml(
    hass: HomeAssistant, mock_clearpass: MagicMock
) -> None:
    """Test the legacy YAML platform imports itself into a config entry."""
    assert await async_setup_component(hass, "device_tracker", YAML_CONFIG)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].source == SOURCE_IMPORT
    assert entries[0].data == MOCK_CONFIG


async def test_setup_scanner_creates_issue_on_cannot_connect(
    hass: HomeAssistant,
    mock_clearpass: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a repair issue is raised when the YAML import cannot connect."""
    mock_clearpass.side_effect = requests.exceptions.ConnectionError

    assert await async_setup_component(hass, "device_tracker", YAML_CONFIG)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_cannot_connect")
    assert issue is not None
    assert issue.translation_placeholders == {"host": MOCK_HOST}
