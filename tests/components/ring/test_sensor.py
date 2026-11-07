"""The tests for the Ring sensor platform."""

from datetime import UTC, datetime
import logging
from typing import cast
from unittest.mock import AsyncMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed, snapshot_platform
from ring_doorbell import Ring
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ring.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .common import MockConfigEntry, async_check_entity_translations, setup_platform
from .device_mocks import FRONT_DOOR_DEVICE_ID


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_ring_client")
async def test_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test states."""
    mock_config_entry.add_to_hass(hass)
    await setup_platform(hass, Platform.SENSOR)
    await async_check_entity_translations(
        hass, entity_registry, mock_config_entry.entry_id, SENSOR_DOMAIN
    )
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("device_name", "sensor_name", "expected_value"),
    [
        ("front_door", "wi_fi_signal_category", "good"),
        ("front_door", "signal_strength", "-58"),
        ("downstairs", "wi_fi_signal_category", "good"),
        ("downstairs", "signal_strength", "-39"),
        ("front", "wi_fi_signal_category", "good"),
        ("front", "signal_strength", "-58"),
    ],
    ids=[
        "doorbell-category",
        "doorbell-strength",
        "chime-category",
        "chime-strength",
        "stickup_cam-category",
        "stickup_cam-strength",
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_ring_client")
async def test_health_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_name: str,
    sensor_name: str,
    expected_value: str,
) -> None:
    """Test the Ring health sensors."""
    entity_id = f"sensor.{device_name}_{sensor_name}"

    await setup_platform(hass, Platform.SENSOR)
    await hass.async_block_till_done()

    sensor_state = hass.states.get(entity_id)
    assert sensor_state is not None
    assert sensor_state.state == "unknown"

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    sensor_state = hass.states.get(entity_id)
    assert sensor_state is not None
    assert sensor_state.state == expected_value


@pytest.mark.parametrize(
    ("device_name", "sensor_name", "expected_value"),
    [
        (
            "front_door",
            "last_activity",
            "2018-03-05T15:03:40+00:00",
        ),
        (
            "front_door",
            "last_recording",
            "2018-03-05T15:03:40+00:00",
        ),
        ("ingress", "last_activity", "2024-02-02T11:21:24+00:00"),
    ],
    ids=[
        "doorbell-activity",
        "doorbell-recording",
        "other-activity",
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_ring_client")
async def test_history_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    device_name: str,
    sensor_name: str,
    expected_value: str,
) -> None:
    """Test the Ring sensors."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.ring.PLATFORMS", [Platform.SENSOR]):
        assert await async_setup_component(hass, DOMAIN, {})

    entity_id = f"sensor.{device_name}_{sensor_name}"
    sensor_state = hass.states.get(entity_id)
    assert sensor_state is not None
    assert sensor_state.state == "unknown"

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    sensor_state = hass.states.get(entity_id)
    assert sensor_state is not None
    assert sensor_state.state == expected_value


async def test_last_recording_sensor_handles_non_ready_history(
    hass: HomeAssistant,
    mock_ring_client: Ring,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the last recording sensor handles non-ready history entries."""
    front_door = cast(Mock, mock_ring_client.devices().get_device(FRONT_DOOR_DEVICE_ID))
    front_door.configure_mock(
        last_history=[
            {
                "created_at": datetime(2019, 3, 5, 15, 3, 40, tzinfo=UTC),
                "recording": {"status": "processing"},
            },
            {
                "created_at": datetime(2018, 3, 5, 15, 3, 40, tzinfo=UTC),
                "recording": {"status": "ready"},
            },
        ]
    )
    mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        domain=SENSOR_DOMAIN,
        platform=DOMAIN,
        unique_id=f"{FRONT_DOOR_DEVICE_ID}-last_recording",
        suggested_object_id="front_door_last_recording",
        config_entry=mock_config_entry,
    )

    with patch("homeassistant.components.ring.PLATFORMS", [Platform.SENSOR]):
        assert await async_setup_component(hass, DOMAIN, {})

    sensor_state = hass.states.get("sensor.front_door_last_recording")
    assert sensor_state is not None
    assert sensor_state.state == "2018-03-05T15:03:40+00:00"

    front_door.configure_mock(
        async_history=AsyncMock(),
        last_history=[
            {
                "created_at": datetime(2020, 3, 5, 15, 3, 40, tzinfo=UTC),
                "recording": {"status": "processing"},
            }
        ],
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    sensor_state = hass.states.get("sensor.front_door_last_recording")
    assert sensor_state is not None
    assert sensor_state.state == "2018-03-05T15:03:40+00:00"


@pytest.mark.usefixtures("mock_ring_client")
async def test_only_chime_devices(
    hass: HomeAssistant,
    mock_ring_devices,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Tests the update service works correctly if only chimes are returned."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")

    mock_ring_devices.all_devices = mock_ring_devices.chimes

    await setup_platform(hass, Platform.SENSOR)
    await hass.async_block_till_done()
    caplog.set_level(logging.DEBUG)
    caplog.clear()
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert "UnboundLocalError" not in caplog.text  # For issue #109210
