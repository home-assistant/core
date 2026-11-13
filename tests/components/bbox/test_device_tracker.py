"""Tests for the Bbox device tracker platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.bbox.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.device_tracker.const import (
    CONF_CONSIDER_HOME,
    CONF_TRACK_NEW,
)
from homeassistant.const import CONF_HOST, STATE_HOME, STATE_NOT_HOME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .const import HOST, HOSTS, NEW_HOST


async def test_device_trackers(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry tracks the known hosts of the main network."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.mylaptop")
    assert state is not None
    assert state.state == STATE_HOME
    state = hass.states.get("device_tracker.oldphone")
    assert state is not None
    assert state.state == STATE_NOT_HOME


async def test_new_device_is_tracked(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device appearing in a later poll gets its tracker entity."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("device_tracker.newtablet") is None

    mock_bbox_client.return_value.get_hosts.return_value = [*HOSTS, NEW_HOST]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("device_tracker.newtablet")
    assert state is not None
    assert state.state == STATE_HOME


async def test_yaml_import(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the legacy device_tracker YAML platform is imported."""
    assert await async_setup_component(
        hass,
        "device_tracker",
        {"device_tracker": {"platform": "bbox", CONF_HOST: HOST}},
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_HOST] == HOST
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_yaml_import_warns_on_dropped_options(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
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
                CONF_CONSIDER_HOME: 300,
                CONF_TRACK_NEW: True,
            }
        },
    )
    await hass.async_block_till_done()

    assert "no longer supported" in caplog.text
    assert CONF_CONSIDER_HOME in caplog.text
    assert CONF_TRACK_NEW in caplog.text
