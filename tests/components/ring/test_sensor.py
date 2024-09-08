"""The tests for the Ring sensor platform."""

import logging
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from ring_doorbell import Ring

from homeassistant.components.ring.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .common import setup_platform
from .device_mocks import FRONT_DEVICE_ID, FRONT_DOOR_DEVICE_ID, INGRESS_DEVICE_ID

from tests.common import async_fire_time_changed


async def test_sensor(hass: HomeAssistant, mock_ring_client) -> None:
    """Test the Ring sensors."""
    await setup_platform(hass, "sensor")

    front_battery_state = hass.states.get("sensor.front_battery")
    assert front_battery_state is not None
    assert front_battery_state.state == "80"
    assert (
        front_battery_state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT
    )

    front_door_battery_state = hass.states.get("sensor.front_door_battery")
    assert front_door_battery_state is not None
    assert front_door_battery_state.state == "100"
    assert (
        front_door_battery_state.attributes[ATTR_STATE_CLASS]
        == SensorStateClass.MEASUREMENT
    )

    downstairs_volume_state = hass.states.get("sensor.downstairs_volume")
    assert downstairs_volume_state is not None
    assert downstairs_volume_state.state == "2"

    ingress_mic_volume_state = hass.states.get("sensor.ingress_mic_volume")
    assert ingress_mic_volume_state.state == "11"

    ingress_doorbell_volume_state = hass.states.get("sensor.ingress_doorbell_volume")
    assert ingress_doorbell_volume_state.state == "8"

    ingress_voice_volume_state = hass.states.get("sensor.ingress_voice_volume")
    assert ingress_voice_volume_state.state == "11"


@pytest.mark.parametrize(
    ("device_id", "device_name", "sensor_name", "expected_value"),
    [
        (987654, "front_door", "wifi_signal_category", "good"),
        (987654, "front_door", "wifi_signal_strength", "-58"),
        (123456, "downstairs", "wifi_signal_category", "good"),
        (123456, "downstairs", "wifi_signal_strength", "-39"),
        (765432, "front", "wifi_signal_category", "good"),
        (765432, "front", "wifi_signal_strength", "-58"),
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
async def test_health_sensor(
    hass: HomeAssistant,
    mock_ring_client,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    device_id,
    device_name,
    sensor_name,
    expected_value,
) -> None:
    """Test the Ring health sensors."""
    entity_id = f"sensor.{device_name}_{sensor_name}"
    # Enable the sensor as the health sensors are disabled by default
    entity_entry = entity_registry.async_get_or_create(
        "sensor",
        "ring",
        f"{device_id}-{sensor_name}",
        suggested_object_id=f"{device_name}_{sensor_name}",
        disabled_by=None,
    )
    assert entity_entry.disabled is False
    assert entity_entry.entity_id == entity_id

    await setup_platform(hass, "sensor")
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
    ("device_id", "device_name", "sensor_name", "expected_value"),
    [
        (
            FRONT_DOOR_DEVICE_ID,
            "front_door",
            "last_motion",
            "2017-03-05T15:03:40+00:00",
        ),
        (FRONT_DOOR_DEVICE_ID, "front_door", "last_ding", "2018-03-05T15:03:40+00:00"),
        (
            FRONT_DOOR_DEVICE_ID,
            "front_door",
            "last_activity",
            "2018-03-05T15:03:40+00:00",
        ),
        (FRONT_DEVICE_ID, "front", "last_motion", "2017-03-05T15:03:40+00:00"),
        (INGRESS_DEVICE_ID, "ingress", "last_activity", "2024-02-02T11:21:24+00:00"),
    ],
    ids=[
        "doorbell-motion",
        "doorbell-ding",
        "doorbell-activity",
        "stickup_cam-motion",
        "other-activity",
    ],
)
async def test_history_sensor(
    hass: HomeAssistant,
    mock_ring_client: Ring,
    mock_config_entry: ConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    device_id: int,
    device_name: str,
    sensor_name: str,
    expected_value: str,
) -> None:
    """Test the Ring sensors."""
    # Create the entity so it is not ignored by the deprecation check
    mock_config_entry.add_to_hass(hass)

    entity_id = f"sensor.{device_name}_{sensor_name}"
    unique_id = f"{device_id}-{sensor_name}"

    entity_registry.async_get_or_create(
        domain=SENSOR_DOMAIN,
        platform=DOMAIN,
        unique_id=unique_id,
        suggested_object_id=f"{device_name}_{sensor_name}",
        config_entry=mock_config_entry,
    )
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


async def test_only_chime_devices(
    hass: HomeAssistant,
    mock_ring_client,
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
