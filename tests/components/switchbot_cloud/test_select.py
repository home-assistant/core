"""Test for the switchbot_cloud select."""

from unittest.mock import AsyncMock, patch

import pytest
from switchbot_api import Device, SwitchBotAPI

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import configure_integration


@pytest.mark.parametrize(
    "device",
    [
        "Standing Fan",
        "Battery Circulator Fan",
        "Battery Circulator Fan 2 Pro",
    ],
)
async def test_night_light_coordinator_data_is_none(
    hass: HomeAssistant,
    mock_list_devices: AsyncMock,
    mock_get_status: AsyncMock,
    device: str,
) -> None:
    """Test coordinator data is none."""

    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="device-id-1",
            deviceName="device-1",
            deviceType=device,
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [None, None]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "select.device_1_night_light"
    state = hass.states.get(entity_id)
    assert state.state == "unknown"


@pytest.mark.parametrize(
    ("key_type", "expected"),
    [
        ("on", "1"),
        ("off", "off"),
        ("bright", "1"),
        ("soft", "2"),
    ],
)
async def test_night_light_options(
    hass: HomeAssistant,
    mock_list_devices: AsyncMock,
    mock_get_status: AsyncMock,
    key_type: str,
    expected: str,
) -> None:
    """Test night light options."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="device-id-1",
            deviceName="device-1",
            deviceType="Standing Fan",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "deviceId": "B0E9FEDEB68C",
            "deviceType": "Standing Fan",
            "power": "on",
            "fanSpeed": 3,
            "mode": "direct",
            "nightStatus": expected,
        },
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "select.device_1_night_light"

    with (
        patch.object(SwitchBotAPI, "send_command") as mocked_send_command,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, "option": key_type},
            blocking=True,
        )

        mocked_send_command.assert_awaited_once()
        assert mocked_send_command.await_args.args[3] == expected

    state = hass.states.get(entity_id)
    assert state.state == key_type


async def test_night_light_options_not_exist(
    hass: HomeAssistant,
    mock_list_devices: AsyncMock,
    mock_get_status: AsyncMock,
) -> None:
    """Test night light options."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="standing-fan-id-1",
            deviceName="standing-fan-1",
            deviceType="Standing Fan",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "deviceId": "B0E9FEDEB68C",
            "deviceType": "Standing Fan",
            "power": "on",
            "fanSpeed": 3,
            "mode": "direct",
            "nightStatus": "fake_option",
        },
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "select.standing_fan_1_night_light"

    state = hass.states.get(entity_id)
    assert state.state == "unknown"
