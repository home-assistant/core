"""Tests for the GeoSphere Austria Warnings sensors."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = pytest.mark.usefixtures("mock_client")


@pytest.mark.freeze_time("2023-03-27 12:00:00+00:00")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the state of the sensors while a warning is active."""
    with patch(
        "homeassistant.components.geosphere_austria_warnings.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2023-03-27 20:00:00+00:00")
async def test_sensors_without_active_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the state of the sensors when no warning is active."""
    with patch(
        "homeassistant.components.geosphere_austria_warnings.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get("sensor.schwechat_warning_level"))
    assert state.state == "none"
    assert (state := hass.states.get("sensor.schwechat_active_warnings"))
    assert state.state == "0"
