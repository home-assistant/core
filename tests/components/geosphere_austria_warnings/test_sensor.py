"""Tests for the GeoSphere Austria Warnings sensors."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pygeosphere_warnings import GeoSphereConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.geosphere_austria_warnings.coordinator import (
    UPDATE_INTERVAL,
)
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

pytestmark = pytest.mark.usefixtures("mock_client")

ACTIVE_WARNINGS_ENTITY_ID = "sensor.schwechat_active_warnings"


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
    assert (state := hass.states.get(ACTIVE_WARNINGS_ENTITY_ID))
    assert state.state == "0"


@pytest.mark.freeze_time("2023-03-27 12:00:00+00:00")
async def test_entities_unavailable_on_error(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that entities become unavailable when the update fails."""
    await setup_integration(hass, mock_config_entry)
    assert (state := hass.states.get(ACTIVE_WARNINGS_ENTITY_ID))
    assert state.state != STATE_UNAVAILABLE

    mock_client.get_last_modified.side_effect = GeoSphereConnectionError
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (state := hass.states.get(ACTIVE_WARNINGS_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE
