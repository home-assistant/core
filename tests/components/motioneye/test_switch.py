"""Tests for the motionEye switch platform."""
import copy
from datetime import timedelta
from unittest.mock import AsyncMock, call, patch

from freezegun.api import FrozenDateTimeFactory
from motioneye_client.const import (
    KEY_MOTION_DETECTION,
    KEY_MOVIES,
    KEY_STILL_IMAGES,
    KEY_TEXT_OVERLAY,
    KEY_UPLOAD_ENABLED,
    KEY_VIDEO_STREAMING,
)

from homeassistant.components.motioneye import get_motioneye_device_identifier
from homeassistant.components.motioneye.const import DEFAULT_SCAN_INTERVAL
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    TEST_CAMERA,
    TEST_CAMERA_ID,
    TEST_CAMERAS,
    TEST_SWITCH_ENTITY_ID_BASE,
    TEST_SWITCH_MOTION_DETECTION_ENTITY_ID,
    create_mock_motioneye_client,
    setup_mock_motioneye_config_entry,
)

from tests.common import async_fire_time_changed


async def test_switch_turn_on_off(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test turning the switch on and off."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    # Verify switch is on.
    entity_state = hass.states.get(TEST_SWITCH_MOTION_DETECTION_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "on"

    client.async_get_camera = AsyncMock(return_value=TEST_CAMERA)

    expected_camera = copy.deepcopy(TEST_CAMERA)
    expected_camera[KEY_MOTION_DETECTION] = False

    # When the next refresh is called return the updated values.
    client.async_get_cameras = AsyncMock(return_value={"cameras": [expected_camera]})

    # Turn switch off.
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_SWITCH_MOTION_DETECTION_ENTITY_ID},
        blocking=True,
    )

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Verify correct parameters are passed to the library.
    assert client.async_set_camera.call_args == call(TEST_CAMERA_ID, expected_camera)

    # Verify the switch turns off.
    entity_state = hass.states.get(TEST_SWITCH_MOTION_DETECTION_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "off"

    # When the next refresh is called return the updated values.
    client.async_get_cameras = AsyncMock(return_value={"cameras": [TEST_CAMERA]})

    # Turn switch on.
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_SWITCH_MOTION_DETECTION_ENTITY_ID},
        blocking=True,
    )

    # Verify correct parameters are passed to the library.
    assert client.async_set_camera.call_args == call(TEST_CAMERA_ID, TEST_CAMERA)

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Verify the switch turns on.
    entity_state = hass.states.get(TEST_SWITCH_MOTION_DETECTION_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "on"


async def test_switch_state_update_from_coordinator(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test that coordinator data impacts state."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    # Verify switch is on.
    entity_state = hass.states.get(TEST_SWITCH_MOTION_DETECTION_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "on"

    updated_cameras = copy.deepcopy(TEST_CAMERAS)
    updated_cameras["cameras"][0][KEY_MOTION_DETECTION] = False
    client.async_get_cameras = AsyncMock(return_value=updated_cameras)

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Verify the switch turns off.
    entity_state = hass.states.get(TEST_SWITCH_MOTION_DETECTION_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "off"


async def test_switch_has_correct_entities(hass: HomeAssistant) -> None:
    """Test that the correct switch entities are created."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    enabled_switch_keys = [
        KEY_MOTION_DETECTION,
        KEY_STILL_IMAGES,
        KEY_MOVIES,
    ]
    disabled_switch_keys = [
        KEY_TEXT_OVERLAY,
        KEY_UPLOAD_ENABLED,
        KEY_VIDEO_STREAMING,
    ]

    for switch_key in enabled_switch_keys:
        entity_id = f"{TEST_SWITCH_ENTITY_ID_BASE}_{switch_key}"
        entity_state = hass.states.get(entity_id)
        assert entity_state, f"Couldn't find entity: {entity_id}"

    for switch_key in disabled_switch_keys:
        entity_id = f"{TEST_SWITCH_ENTITY_ID_BASE}_{switch_key}"
        entity_state = hass.states.get(entity_id)
        assert not entity_state


async def test_disabled_switches_can_be_enabled(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Verify disabled switches can be enabled."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    disabled_switch_keys = [
        KEY_TEXT_OVERLAY,
        KEY_UPLOAD_ENABLED,
    ]

    for switch_key in disabled_switch_keys:
        entity_id = f"{TEST_SWITCH_ENTITY_ID_BASE}_{switch_key}"
        entity_registry = er.async_get(hass)
        entry = entity_registry.async_get(entity_id)
        assert entry
        assert entry.disabled
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        entity_state = hass.states.get(entity_id)
        assert not entity_state

        with patch(
            "homeassistant.components.motioneye.MotionEyeClient",
            return_value=client,
        ):
            updated_entry = entity_registry.async_update_entity(
                entity_id, disabled_by=None
            )
            assert not updated_entry.disabled
            await hass.async_block_till_done()

            freezer.tick(timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()

        entity_state = hass.states.get(entity_id)
        assert entity_state


async def test_switch_device_info(hass: HomeAssistant) -> None:
    """Verify device information includes expected details."""
    config_entry = await setup_mock_motioneye_config_entry(hass)

    device_identifer = get_motioneye_device_identifier(
        config_entry.entry_id, TEST_CAMERA_ID
    )
    device_registry = dr.async_get(hass)

    device = device_registry.async_get_device(identifiers={device_identifer})
    assert device

    entity_registry = er.async_get(hass)
    entities_from_device = [
        entry.entity_id
        for entry in er.async_entries_for_device(entity_registry, device.id)
    ]
    assert TEST_SWITCH_MOTION_DETECTION_ENTITY_ID in entities_from_device
