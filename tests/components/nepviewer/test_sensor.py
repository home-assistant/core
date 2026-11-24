"""Tests for NEPViewer sensor platform."""

import logging
from unittest.mock import MagicMock

from aionepviewer import NepAuthError, NepConnectionError, SiteModulesData
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nepviewer.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

SITE_ENTITY_ID = "sensor.test_site_current_power"
PANEL_ENTITY_ID = "sensor.panel_1_current_power"


@pytest.mark.usefixtures("mock_nepviewer")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor entity registration and states."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nepviewer: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that sensors become unavailable when the API cannot be reached."""
    caplog.set_level(logging.INFO)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(SITE_ENTITY_ID).state == "1500.0"

    mock_nepviewer.get_site_overview.side_effect = NepConnectionError
    for _ in range(2):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get(SITE_ENTITY_ID).state == STATE_UNAVAILABLE
    assert caplog.text.count("nepviewer is unavailable") == 1

    mock_nepviewer.get_site_overview.side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(SITE_ENTITY_ID).state == "1500.0"
    assert caplog.text.count("Fetching nepviewer data recovered") == 1


async def test_missing_panel(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nepviewer: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that only the panel becomes unavailable when it is no longer reported."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(PANEL_ENTITY_ID).state == "750.0"

    mock_nepviewer.get_site_modules.return_value = SiteModulesData({"list": []})
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(PANEL_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(SITE_ENTITY_ID).state == "1500.0"


async def test_reauth_started(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nepviewer: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that rejected credentials start a reauth flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_nepviewer.get_site_overview.side_effect = NepAuthError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(SITE_ENTITY_ID).state == STATE_UNAVAILABLE
    (flow,) = hass.config_entries.flow.async_progress()
    assert flow["context"]["source"] == SOURCE_REAUTH
