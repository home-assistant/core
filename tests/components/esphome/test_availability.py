"""Test ESPHome sub-device availability."""

from aioesphomeapi import (
    APIClient,
    APIVersion,
    BinarySensorInfo,
    BinarySensorState,
    DeviceState,
    SubDeviceInfo,
)
import pytest

from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import MockESPHomeDeviceType


async def test_sub_device_availability_only_affects_its_entities(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a sub-device availability update is scoped by device id."""
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={
            "devices": [
                SubDeviceInfo(device_id=1, name="Sub Device 1"),
                SubDeviceInfo(device_id=2, name="Sub Device 2"),
            ]
        },
        entity_info=[
            BinarySensorInfo(key=1, name="Main", device_id=0),
            BinarySensorInfo(key=1, name="Motion", device_id=1),
            BinarySensorInfo(key=1, name="Motion", device_id=2),
        ],
        states=[
            BinarySensorState(key=1, state=True, device_id=0),
            BinarySensorState(key=1, state=True, device_id=1),
            BinarySensorState(key=1, state=True, device_id=2),
        ],
    )

    mock_device.set_device_state(DeviceState(device_id=1, available=False))
    await hass.async_block_till_done()

    assert hass.states.is_state("binary_sensor.test_main", STATE_ON)
    assert hass.states.is_state("binary_sensor.sub_device_1_motion", STATE_UNAVAILABLE)
    assert hass.states.is_state("binary_sensor.sub_device_2_motion", STATE_ON)

    mock_device.set_device_state(DeviceState(device_id=1, available=True))
    await hass.async_block_till_done()

    assert hass.states.is_state("binary_sensor.sub_device_1_motion", STATE_ON)


@pytest.mark.parametrize(
    ("api_version", "state_after_reconnect"),
    [
        pytest.param(APIVersion(1, 14), STATE_ON, id="unsupported"),
        pytest.param(APIVersion(1, 15), STATE_UNAVAILABLE, id="supported"),
    ],
)
async def test_sub_device_availability_reconnect_behavior_depends_on_api_version(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    api_version: APIVersion,
    state_after_reconnect: str,
) -> None:
    """Test reconnect behavior depends on snapshot support."""
    mock_client.api_version = api_version
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={"devices": [SubDeviceInfo(device_id=1, name="Sub Device")]},
        entity_info=[BinarySensorInfo(key=1, name="Motion", device_id=1)],
        states=[BinarySensorState(key=1, state=True, device_id=1)],
    )

    mock_device.set_device_state(DeviceState(device_id=1, available=False))
    await hass.async_block_till_done()
    assert hass.states.is_state("binary_sensor.sub_device_motion", STATE_UNAVAILABLE)

    await mock_device.mock_disconnect(expected_disconnect=False)
    await mock_device.mock_connect()
    await hass.async_block_till_done()
    assert hass.states.is_state(
        "binary_sensor.sub_device_motion", state_after_reconnect
    )

    mock_device.set_device_state(DeviceState(device_id=1, available=True))
    await hass.async_block_till_done()
    assert hass.states.is_state("binary_sensor.sub_device_motion", STATE_ON)
