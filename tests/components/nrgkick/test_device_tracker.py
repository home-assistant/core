"""Tests for the NRGkick device tracker platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_NOT_HOME, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


async def test_device_tracker_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device tracker entities."""
    await setup_integration(
        hass, mock_config_entry, platforms=[Platform.DEVICE_TRACKER]
    )

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_device_tracker_not_created_without_sim_module(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
) -> None:
    """Test that the device tracker is not created for non-SIM models."""
    mock_nrgkick_api.get_info.return_value["general"]["model_type"] = "NRGkick Gen2"

    await setup_integration(
        hass, mock_config_entry, platforms=[Platform.DEVICE_TRACKER]
    )

    assert hass.states.get("device_tracker.nrgkick_test_gps_tracker") is None


async def test_device_tracker_no_gps_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
) -> None:
    """Test device tracker when GPS data is not available."""
    mock_nrgkick_api.get_info.return_value.pop("gps", None)

    await setup_integration(
        hass, mock_config_entry, platforms=[Platform.DEVICE_TRACKER]
    )

    state = hass.states.get("device_tracker.nrgkick_test_gps_tracker")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert "latitude" not in state.attributes
    assert "longitude" not in state.attributes


async def test_device_tracker_with_gps_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
) -> None:
    """Test device tracker with valid GPS coordinates."""
    await setup_integration(
        hass, mock_config_entry, platforms=[Platform.DEVICE_TRACKER]
    )

    state = hass.states.get("device_tracker.nrgkick_test_gps_tracker")
    assert state is not None
    assert state.state == STATE_NOT_HOME
    assert state.attributes["latitude"] == 47.0748
    assert state.attributes["longitude"] == 15.4376
    assert state.attributes["gps_accuracy"] == 1.5
    assert state.attributes["source_type"] == "gps"
