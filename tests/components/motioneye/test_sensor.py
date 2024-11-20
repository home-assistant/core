"""Tests for the motionEye switch platform."""

import copy
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from motioneye_client.const import KEY_ACTIONS

from homeassistant.components.motioneye import get_motioneye_device_identifier
from homeassistant.components.motioneye.const import (
    DEFAULT_SCAN_INTERVAL,
    TYPE_MOTIONEYE_ACTION_SENSOR,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    TEST_CAMERA,
    TEST_CAMERA_ID,
    TEST_SENSOR_ACTION_ENTITY_ID,
    create_mock_motioneye_client,
    register_test_entity,
    setup_mock_motioneye_config_entry,
)

from tests.common import async_fire_time_changed


async def test_sensor_actions(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the actions sensor."""
    register_test_entity(
        hass,
        SENSOR_DOMAIN,
        TEST_CAMERA_ID,
        TYPE_MOTIONEYE_ACTION_SENSOR,
        TEST_SENSOR_ACTION_ENTITY_ID,
    )

    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    entity_state = hass.states.get(TEST_SENSOR_ACTION_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "3"
    assert entity_state.attributes.get(KEY_ACTIONS) == ["one", "two", "three"]

    updated_camera = copy.deepcopy(TEST_CAMERA)
    updated_camera[KEY_ACTIONS] = ["one"]

    # When the next refresh is called return the updated values.
    client.async_get_cameras = AsyncMock(return_value={"cameras": [updated_camera]})
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity_state = hass.states.get(TEST_SENSOR_ACTION_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "1"
    assert entity_state.attributes.get(KEY_ACTIONS) == ["one"]

    del updated_camera[KEY_ACTIONS]
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity_state = hass.states.get(TEST_SENSOR_ACTION_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "0"
    assert entity_state.attributes.get(KEY_ACTIONS) is None


async def test_sensor_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Verify device information includes expected details."""

    # Enable the action sensor (it is disabled by default).
    register_test_entity(
        hass,
        SENSOR_DOMAIN,
        TEST_CAMERA_ID,
        TYPE_MOTIONEYE_ACTION_SENSOR,
        TEST_SENSOR_ACTION_ENTITY_ID,
    )

    config_entry = await setup_mock_motioneye_config_entry(hass)

    device_identifer = get_motioneye_device_identifier(
        config_entry.entry_id, TEST_CAMERA_ID
    )

    device = device_registry.async_get_device(identifiers={device_identifer})
    assert device

    entities_from_device = [
        entry.entity_id
        for entry in er.async_entries_for_device(entity_registry, device.id)
    ]
    assert TEST_SENSOR_ACTION_ENTITY_ID in entities_from_device


async def test_sensor_actions_can_be_enabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Verify the action sensor can be enabled."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    entry = entity_registry.async_get(TEST_SENSOR_ACTION_ENTITY_ID)
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    entity_state = hass.states.get(TEST_SENSOR_ACTION_ENTITY_ID)
    assert not entity_state

    with patch(
        "homeassistant.components.motioneye.MotionEyeClient",
        return_value=client,
    ):
        updated_entry = entity_registry.async_update_entity(
            TEST_SENSOR_ACTION_ENTITY_ID, disabled_by=None
        )
        assert not updated_entry.disabled
        await hass.async_block_till_done()

        freezer.tick(timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    entity_state = hass.states.get(TEST_SENSOR_ACTION_ENTITY_ID)
    assert entity_state
