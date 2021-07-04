"""Tests for the motionEye binary sensor platform."""
from __future__ import annotations

import datetime
from datetime import timedelta
import logging
from unittest.mock import patch

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    DOMAIN as BINARY_SENSOR_DOMAIN,
)
from homeassistant.components.motioneye import get_motioneye_device_identifier
from homeassistant.components.motioneye.const import (
    CONF_EVENT_DURATION,
    DOMAIN,
    EVENT_FILE_STORED,
    EVENT_MOTION_DETECTED,
    TYPE_MOTIONEYE_MOTION_BINARY_SENSOR,
)
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.util.dt as dt_util

from . import (
    TEST_BINARY_SENSOR_FILE_STORED_ENTITY_ID,
    TEST_BINARY_SENSOR_MOTION_ENTITY_ID,
    TEST_CAMERA_ID,
    create_mock_motioneye_client,
    register_test_entity,
    setup_mock_motioneye_config_entry,
)

from tests.common import async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


async def test_binary_sensor_events(hass: HomeAssistant) -> None:
    """Test the actions sensor."""

    async def fire_event(
        now: datetime.datetime, event_type: str, device_id: str | None = None
    ) -> None:
        """Fire an event."""
        with patch("homeassistant.helpers.event.dt_util.utcnow", return_value=now):
            hass.bus.async_fire(
                f"{DOMAIN}.{event_type}",
                {CONF_DEVICE_ID: device_id} if device_id else {},
            )
            await hass.async_block_till_done()

    register_test_entity(
        hass,
        BINARY_SENSOR_DOMAIN,
        TEST_CAMERA_ID,
        TYPE_MOTIONEYE_MOTION_BINARY_SENSOR,
        TEST_BINARY_SENSOR_MOTION_ENTITY_ID,
    )

    device_registry = dr.async_get(hass)
    client = create_mock_motioneye_client()
    config_entry = await setup_mock_motioneye_config_entry(hass, client=client)
    device_identifer = get_motioneye_device_identifier(
        config_entry.entry_id, TEST_CAMERA_ID
    )
    device = device_registry.async_get_device({device_identifer})
    assert device

    now = dt_util.utcnow()

    # Ensure it starts off...
    entity_state = hass.states.get(TEST_BINARY_SENSOR_MOTION_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "off"

    # ... motion is detected ...
    await fire_event(now, EVENT_MOTION_DETECTED, device.id)

    # ... state should now be on ...
    entity_state = hass.states.get(TEST_BINARY_SENSOR_MOTION_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "on"

    # ... 10 seconds elapses ...
    now += timedelta(seconds=10)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    # ... still should still be on ...
    entity_state = hass.states.get(TEST_BINARY_SENSOR_MOTION_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "on"

    # ... motion is detected again ...
    await fire_event(now, EVENT_MOTION_DETECTED, device.id)

    # ... 21 seconds later it should still be on ...
    now += timedelta(seconds=21)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    entity_state = hass.states.get(TEST_BINARY_SENSOR_MOTION_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "on"

    # ... but after a further 10 seconds it should be back off.
    now += timedelta(seconds=10)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    entity_state = hass.states.get(TEST_BINARY_SENSOR_MOTION_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "off"

    # Now a different device detects motion.
    await fire_event(now, EVENT_MOTION_DETECTED, "different-id")

    entity_state = hass.states.get(TEST_BINARY_SENSOR_MOTION_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "off"

    # Test storing a file.
    await fire_event(now, EVENT_FILE_STORED, device.id)

    entity_state = hass.states.get(TEST_BINARY_SENSOR_MOTION_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "off"

    entity_state = hass.states.get(TEST_BINARY_SENSOR_FILE_STORED_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "on"

    now += timedelta(seconds=31)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    entity_state = hass.states.get(TEST_BINARY_SENSOR_FILE_STORED_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "off"

    # Test missing device id.
    await fire_event(now, EVENT_FILE_STORED)

    entity_state = hass.states.get(TEST_BINARY_SENSOR_MOTION_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "off"

    entity_state = hass.states.get(TEST_BINARY_SENSOR_FILE_STORED_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "off"

    # Reload with a larger event duration.
    with patch(
        "homeassistant.components.motioneye.MotionEyeClient",
        return_value=client,
    ):
        hass.config_entries.async_update_entry(
            config_entry, options={CONF_EVENT_DURATION: 600}
        )
        await hass.async_block_till_done()

    await fire_event(now, EVENT_MOTION_DETECTED, device.id)
    now += timedelta(seconds=32)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    entity_state = hass.states.get(TEST_BINARY_SENSOR_MOTION_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "on"


async def test_binary_sensor_device_info(hass: HomeAssistant) -> None:
    """Verify device information includes expected details."""
    config_entry = await setup_mock_motioneye_config_entry(hass)

    device_identifer = get_motioneye_device_identifier(
        config_entry.entry_id, TEST_CAMERA_ID
    )

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({device_identifer})
    assert device

    entity_registry = await er.async_get_registry(hass)
    entities_from_device = [
        entry.entity_id
        for entry in er.async_entries_for_device(entity_registry, device.id)
    ]
    assert TEST_BINARY_SENSOR_MOTION_ENTITY_ID in entities_from_device


async def test_binary_sensor_device_class(hass: HomeAssistant) -> None:
    """Verify device information includes expected details."""
    await setup_mock_motioneye_config_entry(hass)

    entity_state = hass.states.get(TEST_BINARY_SENSOR_MOTION_ENTITY_ID)
    assert entity_state
    assert entity_state.attributes.get("device_class") == DEVICE_CLASS_MOTION

    entity_state = hass.states.get(TEST_BINARY_SENSOR_FILE_STORED_ENTITY_ID)
    assert entity_state
    assert "device_class" not in entity_state.attributes
