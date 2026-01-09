"""Test the Tesla Fleet update platform."""

import copy
import time
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.tesla_fleet.coordinator import VEHICLE_INTERVAL
from homeassistant.components.tesla_fleet.update import INSTALLING, SCHEDULED
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN, SERVICE_INSTALL
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, setup_platform
from .const import COMMAND_OK, VEHICLE_DATA, VEHICLE_DATA_ALT

from tests.common import MockConfigEntry, async_fire_time_changed


def _get_software_update(data: dict[str, Any]) -> dict[str, Any]:
    """Get the software_update dict from vehicle data."""
    return data["response"]["vehicle_state"]["software_update"]


async def test_update(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Tests that the update entities are correct."""

    await setup_platform(hass, normal_config_entry, [Platform.UPDATE])
    assert_entities(hass, normal_config_entry.entry_id, entity_registry, snapshot)


async def test_update_alt(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    normal_config_entry: MockConfigEntry,
    mock_vehicle_data: AsyncMock,
) -> None:
    """Tests that the update entities are correct."""

    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    await setup_platform(hass, normal_config_entry, [Platform.UPDATE])
    assert_entities(hass, normal_config_entry.entry_id, entity_registry, snapshot)


async def test_update_services(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_vehicle_data: AsyncMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Tests that the update services work."""

    await setup_platform(hass, normal_config_entry, [Platform.UPDATE])

    entity_id = "update.test_update"

    with patch(
        "tesla_fleet_api.tesla.VehicleFleet.schedule_software_update",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        call.assert_called_once()

    vehicle_installing = copy.deepcopy(VEHICLE_DATA)
    _get_software_update(vehicle_installing)["status"] = INSTALLING
    mock_vehicle_data.return_value = vehicle_installing
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["in_progress"] is True


async def test_update_scheduled_far_future_not_in_progress(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_vehicle_data: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Tests that a scheduled update far in the future is not shown as in_progress."""

    await setup_platform(hass, normal_config_entry, [Platform.UPDATE])

    entity_id = "update.test_update"

    # Verify initial state (available) is not in_progress
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["in_progress"] is False

    # Simulate update being scheduled for 1 hour in the future
    vehicle_scheduled = copy.deepcopy(VEHICLE_DATA)
    software_update = _get_software_update(vehicle_scheduled)
    software_update["status"] = SCHEDULED
    # Set scheduled time to 1 hour from now (well beyond threshold)
    software_update["scheduled_time_ms"] = int((time.time() + 3600) * 1000)
    mock_vehicle_data.return_value = vehicle_scheduled
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Scheduled update far in future should NOT be in_progress
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["in_progress"] is False


async def test_update_scheduled_soon_in_progress(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_vehicle_data: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Tests that a scheduled update within threshold is shown as in_progress."""

    await setup_platform(hass, normal_config_entry, [Platform.UPDATE])

    entity_id = "update.test_update"

    # Simulate update being scheduled within threshold (1 minute from now)
    vehicle_scheduled = copy.deepcopy(VEHICLE_DATA)
    software_update = _get_software_update(vehicle_scheduled)
    software_update["status"] = SCHEDULED
    # Set scheduled time to 1 minute from now (within 2 minute threshold)
    software_update["scheduled_time_ms"] = int((time.time() + 60) * 1000)
    mock_vehicle_data.return_value = vehicle_scheduled
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Scheduled update within threshold should be in_progress
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["in_progress"] is True


async def test_update_scheduled_no_time_not_in_progress(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_vehicle_data: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Tests that a scheduled update without scheduled_time_ms is not in_progress."""

    await setup_platform(hass, normal_config_entry, [Platform.UPDATE])

    entity_id = "update.test_update"

    # Simulate update being scheduled but without scheduled_time_ms
    vehicle_scheduled = copy.deepcopy(VEHICLE_DATA)
    _get_software_update(vehicle_scheduled)["status"] = SCHEDULED
    # No scheduled_time_ms field
    mock_vehicle_data.return_value = vehicle_scheduled
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Scheduled update without time should NOT be in_progress
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["in_progress"] is False
