"""Test for the switchbot_cloud select."""

from unittest.mock import patch

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


async def test_keypad_coordinator_data_is_none(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test coordinator data is none."""

    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="keypad-vision-pro-id-1",
            deviceName="keypad-vision-pro-1",
            deviceType="Keypad Vision Pro",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [None, None]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "select.keypad_vision_pro_1"
    state = hass.states.get(entity_id)
    assert state.state == "create key"


@pytest.mark.parametrize(
    ("key_status", "key_type", "result"),
    [
        ("permanent", "normal", ""),
        ("disposable", "normal", ""),
        ("disposable", "expired", " - expired"),
    ],
)
async def test_keypad_key_is_normal(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    key_status,
    key_type,
    result,
) -> None:
    """Test keypad key list state with different key types and statuses."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="keypad-vision-pro-id-1",
            deviceName="keypad-vision-pro-1",
            deviceType="Keypad Vision Pro",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "deviceId": "B0E9FEDEB68C",
            "deviceType": "Keypad Vision Pro",
            "keyList": [
                {
                    "id": 11,
                    "name": "permanent1",
                    "type": key_status,
                    "status": key_type,
                    "createTime": 1772010135000,
                    "password": "vK2gtIy2mNa4QRjiV/7Cpg==",
                    "iv": "c64566e3716ea13b43abbbd3a05861f7",
                },
            ],
        }
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "select.keypad_vision_pro_1"
    state = hass.states.get(entity_id)
    assert state.state == result


async def test_keypad_create_key(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
) -> None:
    """Test keypad create key."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="keypad-vision-pro-id-1",
            deviceName="keypad-vision-pro-1",
            deviceType="Keypad Vision Pro",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "deviceId": "B0E9FEDEB68C",
            "deviceType": "Keypad Vision Pro",
            "keyList": [
                {
                    "id": 11,
                    "name": "permanent1",
                    "type": "disposable",
                    "status": "normal",
                    "createTime": 1772010135000,
                    "password": "vK2gtIy2mNa4QRjiV/7Cpg==",
                    "iv": "c64566e3716ea13b43abbbd3a05861f7",
                },
            ],
        },
        {
            "deviceId": "B0E9FEDEB68C",
            "deviceType": "Keypad Vision Pro",
            "keyList": [
                {
                    "id": 11,
                    "name": "permanent1",
                    "type": "disposable",
                    "status": "normal",
                    "createTime": 1772010135000,
                    "password": "vK2gtIy2mNa4QRjiV/7Cpg==",
                    "iv": "c64566e3716ea13b43abbbd3a05861f7",
                },
            ],
        },
        {
            "deviceId": "B0E9FEDEB68C",
            "deviceType": "Keypad Vision Pro",
            "keyList": [
                {
                    "id": 11,
                    "name": "permanent1",
                    "type": "disposable",
                    "status": "normal",
                    "createTime": 1772010135000,
                    "password": "vK2gtIy2mNa4QRjiV/7Cpg==",
                    "iv": "c64566e3716ea13b43abbbd3a05861f7",
                },
            ],
        },
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "select.keypad_vision_pro_1"

    with (
        patch.object(SwitchBotAPI, "send_command") as mocked_send_command,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, "option": "create key"},
            blocking=True,
        )

        mocked_send_command.assert_called_once()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, "option": ""},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == ""
