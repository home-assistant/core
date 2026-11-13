"""Tests for the Bbox device tracker platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.bbox.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.device_tracker.const import (
    ATTR_IP,
    CONF_CONSIDER_HOME,
    CONF_TRACK_NEW,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from .const import ACTIVE_HOST, HOST, HOSTS, NEW_HOST, PASSWORD

MYLAPTOP_ENTITY = "device_tracker.mylaptop"
OLDPHONE_ENTITY = "device_tracker.oldphone"
NEWTABLET_ENTITY = "device_tracker.newtablet"


async def _async_enable_trackers(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    *entity_ids: str,
) -> None:
    """Enable disabled-by-default tracker entities and reload the entry."""
    for entity_id in entity_ids:
        registry_entry = entity_registry.async_get(entity_id)
        assert registry_entry is not None
        assert registry_entry.disabled_by is not None
        entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.async_block_till_done()
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_bbox_client")
async def test_device_trackers_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the entry creates trackers disabled until enabled explicitly."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for entity_id in (MYLAPTOP_ENTITY, OLDPHONE_ENTITY):
        registry_entry = entity_registry.async_get(entity_id)
        assert registry_entry is not None
        assert registry_entry.disabled_by is not None
        assert hass.states.get(entity_id) is None

    await _async_enable_trackers(
        hass,
        mock_config_entry,
        entity_registry,
        MYLAPTOP_ENTITY,
        OLDPHONE_ENTITY,
    )
    state = hass.states.get(MYLAPTOP_ENTITY)
    assert state is not None
    assert state.state == STATE_HOME
    state = hass.states.get(OLDPHONE_ENTITY)
    assert state is not None
    assert state.state == STATE_NOT_HOME


async def test_new_device_is_tracked(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device appearing in a later poll gets its tracker entity."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await _async_enable_trackers(
        hass,
        mock_config_entry,
        entity_registry,
        MYLAPTOP_ENTITY,
        OLDPHONE_ENTITY,
    )

    mock_bbox_client.return_value.get_hosts.return_value = [*HOSTS, NEW_HOST]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # The new tracker is created disabled by default.
    assert hass.states.get(NEWTABLET_ENTITY) is None
    await _async_enable_trackers(
        hass, mock_config_entry, entity_registry, NEWTABLET_ENTITY
    )
    state = hass.states.get(NEWTABLET_ENTITY)
    assert state is not None
    assert state.state == STATE_HOME


@pytest.mark.usefixtures("mock_bbox_client")
async def test_yaml_scanner_kept_until_2027_5(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the legacy YAML scanner still tracks and is not auto-imported."""
    assert await async_setup_component(
        hass,
        "device_tracker",
        {
            "device_tracker": [
                {
                    "platform": "bbox",
                    CONF_HOST: HOST,
                    CONF_PASSWORD: PASSWORD,
                    CONF_TRACK_NEW: True,
                }
            ]
        },
    )
    await hass.async_block_till_done()

    # No config entry is imported for the device_tracker YAML platform.
    assert not hass.config_entries.async_entries(DOMAIN)
    # The legacy scanner still reports the active hosts.
    state = hass.states.get(MYLAPTOP_ENTITY)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes[ATTR_IP] == ACTIVE_HOST.ipaddress
    # A manual-migration repair is raised instead of an automatic import.
    issue = issue_registry.async_get_issue(DOMAIN, f"migrate_device_tracker_{DOMAIN}")
    assert issue is not None
    assert issue.breaks_in_ha_version == "2027.5.0"


@pytest.mark.usefixtures("mock_bbox_client")
async def test_yaml_scanner_warns_on_dropped_options(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test legacy options that are no longer supported raise a warning."""
    assert await async_setup_component(
        hass,
        "device_tracker",
        {
            "device_tracker": {
                "platform": "bbox",
                CONF_HOST: HOST,
                CONF_PASSWORD: PASSWORD,
                CONF_CONSIDER_HOME: 300,
                CONF_TRACK_NEW: True,
            }
        },
    )
    await hass.async_block_till_done()

    assert "no longer supported" in caplog.text
    assert CONF_CONSIDER_HOME in caplog.text
    assert CONF_TRACK_NEW in caplog.text
