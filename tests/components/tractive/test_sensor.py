"""Test the Tractive sensor platform."""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.tractive.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    ("status_event", "expected_state"),
    [
        pytest.param(
            {
                "tracker_state": "NOT_REPORTING",
                "tracker_state_reason": "SHUTDOWN_BY_USER",
            },
            "system_shutdown_user",
            id="shutdown-without-hardware",
        ),
        pytest.param(
            {
                "tracker_state": "NOT_REPORTING",
                "tracker_state_reason": "SHUTDOWN_BY_USER",
                "hardware": {"time": 1741436626, "battery_level": 99},
                "charging_state": "NOT_CHARGING",
                "position": {
                    "time": 1741436626,
                    "latlong": [33.444, 55.666],
                    "accuracy": 30,
                    "sensor_used": "GPS",
                },
            },
            "system_shutdown_user",
            id="shutdown-with-unchanged-hardware-time",
        ),
        pytest.param(
            {"tracker_state": "NOT_REPORTING"},
            "not_reporting",
            id="not-reporting-without-reason",
        ),
        pytest.param(
            {"tracker_state": "NOT_REPORTING", "tracker_state_reason": "NO_SIGNAL"},
            "not_reporting",
            id="not-reporting-for-another-reason",
        ),
        pytest.param(
            {
                "tracker_state": "OPERATIONAL",
                "tracker_state_reason": "SHUTDOWN_BY_USER",
            },
            "operational",
            id="operational-with-inconsistent-reason",
        ),
        pytest.param(
            {"tracker_state": "SYSTEM_SHUTDOWN_USER"},
            "system_shutdown_user",
            id="legacy-shutdown-state",
        ),
        pytest.param(
            {"tracker_state_reason": "SHUTDOWN_BY_USER"},
            "operational",
            id="reason-without-state-is-not-shutdown",
        ),
        pytest.param(
            {
                "tracker_id": "another_tracker",
                "tracker_state": "NOT_REPORTING",
                "tracker_state_reason": "SHUTDOWN_BY_USER",
            },
            "operational",
            id="another-tracker-does-not-change-state",
        ),
    ],
)
async def test_tracker_state_events(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    status_event: dict[str, Any],
    expected_state: str,
) -> None:
    """Process tracker state separately from the last hardware sample."""
    await init_integration(hass, mock_config_entry)

    async def events() -> AsyncGenerator[dict[str, Any]]:
        yield {
            "message": "tracker_status",
            "tracker_id": "device_id_123",
            "tracker_state": "OPERATIONAL",
            "hardware": {"time": 1741436626, "battery_level": 98},
            "charging_state": "NOT_CHARGING",
            "position": {
                "time": 1741436626,
                "latlong": [22.333, 44.555],
                "accuracy": 30,
                "sensor_used": "GPS",
            },
        }
        yield {
            "message": "tracker_status",
            "tracker_id": "device_id_123",
            **status_event,
        }
        raise asyncio.CancelledError

    mock_tractive_client.events.side_effect = events
    with pytest.raises(asyncio.CancelledError):
        await mock_config_entry.runtime_data.client._listen()
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.tracker_device_id_123_status"))
    assert state.state == expected_state
    assert (battery := hass.states.get("sensor.tracker_device_id_123_battery"))
    assert battery.state == "98"
    assert (position := hass.states.get("device_tracker.tracker_device_id_123"))
    assert position.attributes["latitude"] == 22.333
    assert position.attributes["longitude"] == 44.555


@pytest.mark.parametrize(
    ("following_event", "expected_state"),
    [
        pytest.param({"tracker_state": "OPERATIONAL"}, "operational", id="powered-on"),
        pytest.param(
            {"tracker_state": "NOT_REPORTING"},
            "not_reporting",
            id="shutdown-reason-not-reused",
        ),
        pytest.param(
            {"tracker_state_reason": "SHUTDOWN_BY_USER"},
            "system_shutdown_user",
            id="reason-only-does-not-change-state",
        ),
        pytest.param(
            {"hardware": {"time": 1741436626, "battery_level": 98}},
            "system_shutdown_user",
            id="hardware-only-does-not-change-state",
        ),
    ],
)
async def test_tracker_state_after_shutdown(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    following_event: dict[str, Any],
    expected_state: str,
) -> None:
    """Apply subsequent states without retaining a previous shutdown reason."""
    await init_integration(hass, mock_config_entry)

    async def events() -> AsyncGenerator[dict[str, Any]]:
        yield {
            "message": "tracker_status",
            "tracker_id": "device_id_123",
            "tracker_state": "NOT_REPORTING",
            "tracker_state_reason": "SHUTDOWN_BY_USER",
        }
        yield {
            "message": "tracker_status",
            "tracker_id": "device_id_123",
            "charging_state": "NOT_CHARGING",
            **following_event,
        }
        raise asyncio.CancelledError

    mock_tractive_client.events.side_effect = events
    with pytest.raises(asyncio.CancelledError):
        await mock_config_entry.runtime_data.client._listen()
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.tracker_device_id_123_status"))
    assert state.state == expected_state


async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the sensor."""
    with patch("homeassistant.components.tractive.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

        mock_tractive_client.send_hardware_event(mock_config_entry)
        mock_tractive_client.send_health_overview_event(mock_config_entry)
        await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_device_assignment(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that hardware sensors are on the tracker device and health sensors on the pet device."""
    with patch("homeassistant.components.tractive.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    tracker_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "device_id_123"), mock_config_entry.entry_id
    )
    assert tracker_device is not None

    pet_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "pet_id_123"), mock_config_entry.entry_id
    )
    assert pet_device is not None
    assert pet_device.via_device_id == tracker_device.id

    for entity_id in (
        "sensor.tracker_device_id_123_battery",
        "sensor.tracker_device_id_123_status",
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.device_id == tracker_device.id

    for entity_id in (
        "sensor.test_pet_activity_time",
        "sensor.test_pet_rest_time",
        "sensor.test_pet_daily_goal",
        "sensor.test_pet_day_sleep",
        "sensor.test_pet_night_sleep",
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.device_id == pet_device.id
