"""Tests for the GeoSphere Austria Warnings sensors."""

from typing import Any
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pygeosphere_warnings import GeoSphereConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.geosphere_austria_warnings.const import DOMAIN
from homeassistant.components.geosphere_austria_warnings.coordinator import (
    UPDATE_INTERVAL,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

pytestmark = pytest.mark.usefixtures("mock_client")

WARNING_LEVEL_ENTITY_ID = "sensor.schwechat_warning_level"
ACTIVE_WARNINGS_ENTITY_ID = "sensor.schwechat_active_warnings"
ADVANCE_WARNING_LEVEL_ENTITY_ID = "sensor.schwechat_advance_warning_level"
ADVANCE_WARNINGS_ENTITY_ID = "sensor.schwechat_advance_warnings"

EXPECTED_ENTITY_IDS = {
    WARNING_LEVEL_ENTITY_ID,
    ACTIVE_WARNINGS_ENTITY_ID,
    ADVANCE_WARNING_LEVEL_ENTITY_ID,
    ADVANCE_WARNINGS_ENTITY_ID,
}

WARNING_DETAIL_ATTRIBUTE_KEYS = {"type", "start", "end", "warning_id"}


def warning_details(state: State) -> dict[str, Any]:
    """Return integration-specific warning attributes only."""
    return {
        key: value
        for key, value in state.attributes.items()
        if key in WARNING_DETAIL_ATTRIBUTE_KEYS
    }


@pytest.mark.freeze_time("2023-03-27 12:00:00+00:00")
async def test_sensor_set_and_active_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the complete sensor set while a warning is active."""
    await setup_integration(hass, mock_config_entry)

    entity_ids = {
        entity_id
        for entity_id in hass.states.async_entity_ids("sensor")
        if entity_id.startswith("sensor.schwechat_")
    }
    assert entity_ids == EXPECTED_ENTITY_IDS

    assert (state := hass.states.get(WARNING_LEVEL_ENTITY_ID))
    assert state.state == "orange"
    assert warning_details(state) == {
        "type": "storm",
        "start": "2023-03-27T08:00:00+00:00",
        "end": "2023-03-27T18:00:00+00:00",
        "warning_id": 4149,
    }

    assert (state := hass.states.get(ACTIVE_WARNINGS_ENTITY_ID))
    assert state.state == "2"

    assert (state := hass.states.get(ADVANCE_WARNING_LEVEL_ENTITY_ID))
    assert state.state == "orange"
    assert warning_details(state) == {
        "type": "rain",
        "start": "2023-03-28T06:00:00+00:00",
        "end": "2023-03-28T16:00:00+00:00",
        "warning_id": 4150,
    }

    assert (state := hass.states.get(ADVANCE_WARNINGS_ENTITY_ID))
    assert state.state == "5"

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "30740"), mock_config_entry.entry_id
    )
    assert device_entry
    assert device_entry == snapshot


@pytest.mark.freeze_time("2023-03-28 00:00:00+00:00")
async def test_sensors_without_active_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor states and empty attributes when no warning is active."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(WARNING_LEVEL_ENTITY_ID))
    assert state.state == "none"
    assert warning_details(state) == {}

    assert (state := hass.states.get(ACTIVE_WARNINGS_ENTITY_ID))
    assert state.state == "0"

    assert (state := hass.states.get(ADVANCE_WARNING_LEVEL_ENTITY_ID))
    assert state.state == "orange"
    assert warning_details(state) == {
        "type": "rain",
        "start": "2023-03-28T06:00:00+00:00",
        "end": "2023-03-28T16:00:00+00:00",
        "warning_id": 4150,
    }

    assert (state := hass.states.get(ADVANCE_WARNINGS_ENTITY_ID))
    assert state.state == "5"


@pytest.mark.freeze_time("2023-03-27 12:00:00+00:00")
async def test_entities_unavailable_on_error(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that entities become unavailable when the update fails."""
    await setup_integration(hass, mock_config_entry)
    for entity_id in EXPECTED_ENTITY_IDS:
        assert (state := hass.states.get(entity_id))
        assert state.state != STATE_UNAVAILABLE

    mock_client.get_last_modified.side_effect = GeoSphereConnectionError
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for entity_id in EXPECTED_ENTITY_IDS:
        assert (state := hass.states.get(entity_id))
        assert state.state == STATE_UNAVAILABLE
