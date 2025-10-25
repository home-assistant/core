"""Test ESPHome binary sensors."""

from aioesphomeapi import APIClient, BinarySensorInfo, BinarySensorState, SubDeviceInfo
import pytest

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import MockESPHomeDeviceType, MockGenericDeviceEntryType


@pytest.mark.parametrize(
    "binary_state", [(True, STATE_ON), (False, STATE_OFF), (None, STATE_UNKNOWN)]
)
async def test_binary_sensor_generic_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    binary_state: tuple[bool, str],
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic binary_sensor entity."""
    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="my binary_sensor",
        )
    ]
    esphome_state, hass_state = binary_state
    states = [BinarySensorState(key=1, state=esphome_state)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("binary_sensor.test_my_binary_sensor")
    assert state is not None
    assert state.state == hass_state


async def test_status_binary_sensor(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic binary_sensor entity."""
    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="my binary_sensor",
            is_status_binary_sensor=True,
        )
    ]
    states = [BinarySensorState(key=1, state=None)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("binary_sensor.test_my_binary_sensor")
    assert state is not None
    assert state.state == STATE_ON


async def test_binary_sensor_missing_state(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic binary_sensor that is missing state."""
    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="my binary_sensor",
        )
    ]
    states = [BinarySensorState(key=1, state=True, missing_state=True)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("binary_sensor.test_my_binary_sensor")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_binary_sensor_has_state_false(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a generic binary_sensor where has_state is false."""
    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="my binary_sensor",
        )
    ]
    states = []
    user_service = []
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("binary_sensor.test_my_binary_sensor")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    mock_device.set_state(BinarySensorState(key=1, state=True, missing_state=False))
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_my_binary_sensor")
    assert state is not None
    assert state.state == STATE_ON


async def test_binary_sensors_same_key_different_device_id(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test binary sensors with same key but different device_id."""
    # Create sub-devices
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="Sub Device 1", area_id=0),
        SubDeviceInfo(device_id=22222222, name="Sub Device 2", area_id=0),
    ]

    device_info = {
        "name": "test",
        "devices": sub_devices,
    }

    # Both sub-devices have a binary sensor with key=1
    entity_info = [
        BinarySensorInfo(
            object_id="sensor",
            key=1,
            name="Motion",
            device_id=11111111,
        ),
        BinarySensorInfo(
            object_id="sensor",
            key=1,
            name="Motion",
            device_id=22222222,
        ),
    ]

    # States for both sensors with same key but different device_id
    states = [
        BinarySensorState(key=1, state=True, missing_state=False, device_id=11111111),
        BinarySensorState(key=1, state=False, missing_state=False, device_id=22222222),
    ]

    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )

    # Verify both entities exist and have correct states
    state1 = hass.states.get("binary_sensor.sub_device_1_motion")
    assert state1 is not None
    assert state1.state == STATE_ON

    state2 = hass.states.get("binary_sensor.sub_device_2_motion")
    assert state2 is not None
    assert state2.state == STATE_OFF

    # Update states to verify they update independently
    mock_device.set_state(
        BinarySensorState(key=1, state=False, missing_state=False, device_id=11111111)
    )
    await hass.async_block_till_done()

    state1 = hass.states.get("binary_sensor.sub_device_1_motion")
    assert state1.state == STATE_OFF

    # Sub device 2 should remain unchanged
    state2 = hass.states.get("binary_sensor.sub_device_2_motion")
    assert state2.state == STATE_OFF

    # Update sub device 2
    mock_device.set_state(
        BinarySensorState(key=1, state=True, missing_state=False, device_id=22222222)
    )
    await hass.async_block_till_done()

    state2 = hass.states.get("binary_sensor.sub_device_2_motion")
    assert state2.state == STATE_ON

    # Sub device 1 should remain unchanged
    state1 = hass.states.get("binary_sensor.sub_device_1_motion")
    assert state1.state == STATE_OFF


async def test_binary_sensor_main_and_sub_device_same_key(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test binary sensor on main device and sub-device with same key."""
    # Create sub-device
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="Sub Device", area_id=0),
    ]

    device_info = {
        "name": "test",
        "devices": sub_devices,
    }

    # Main device and sub-device both have a binary sensor with key=1
    entity_info = [
        BinarySensorInfo(
            object_id="main_sensor",
            key=1,
            name="Main Sensor",
            device_id=0,  # Main device
        ),
        BinarySensorInfo(
            object_id="sub_sensor",
            key=1,
            name="Sub Sensor",
            device_id=11111111,
        ),
    ]

    # States for both sensors
    states = [
        BinarySensorState(key=1, state=True, missing_state=False, device_id=0),
        BinarySensorState(key=1, state=False, missing_state=False, device_id=11111111),
    ]

    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )

    # Verify both entities exist
    main_state = hass.states.get("binary_sensor.test_main_sensor")
    assert main_state is not None
    assert main_state.state == STATE_ON

    sub_state = hass.states.get("binary_sensor.sub_device_sub_sensor")
    assert sub_state is not None
    assert sub_state.state == STATE_OFF

    # Update main device sensor
    mock_device.set_state(
        BinarySensorState(key=1, state=False, missing_state=False, device_id=0)
    )
    await hass.async_block_till_done()

    main_state = hass.states.get("binary_sensor.test_main_sensor")
    assert main_state.state == STATE_OFF

    # Sub device sensor should remain unchanged
    sub_state = hass.states.get("binary_sensor.sub_device_sub_sensor")
    assert sub_state.state == STATE_OFF
