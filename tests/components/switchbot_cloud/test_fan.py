"""Test for the Switchbot Battery Circulator Fan."""

from unittest.mock import patch

import pytest
import switchbot_api
from switchbot_api import Device, SwitchBotAPI
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_TURN_ON,
)
from homeassistant.components.switchbot_cloud.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import AIR_PURIFIER_INFO, CIRCULATOR_FAN_INFO, configure_integration

from tests.common import async_load_json_object_fixture, snapshot_platform


@pytest.mark.parametrize(
    ("device_info", "entry_id"),
    [
        (AIR_PURIFIER_INFO, "fan.air_purifier_1"),
        (CIRCULATOR_FAN_INFO, "fan.battery_fan_1"),
    ],
)
async def test_coordinator_data_is_none(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    device_info: Device,
    entry_id: str,
) -> None:
    """Test coordinator data is none."""
    mock_list_devices.return_value = [device_info]
    mock_get_status.side_effect = [None]

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    state = hass.states.get(entry_id)

    assert state.state == STATE_UNKNOWN


async def test_turn_on(hass: HomeAssistant, mock_list_devices, mock_get_status) -> None:
    """Test turning on the fan."""
    mock_list_devices.return_value = [
        CIRCULATOR_FAN_INFO,
    ]
    mock_get_status.side_effect = [
        {"power": "off", "mode": "direct", "fanSpeed": "0"},
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_OFF

    with (
        patch.object(SwitchBotAPI, "send_command") as mock_send_command,
    ):
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    mock_send_command.assert_called()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_turn_off(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turning off the fan."""
    mock_list_devices.return_value = [
        CIRCULATOR_FAN_INFO,
    ]
    mock_get_status.side_effect = [
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
        {"power": "off", "mode": "direct", "fanSpeed": "0"},
        {"power": "off", "mode": "direct", "fanSpeed": "0"},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_ON

    with (
        patch.object(SwitchBotAPI, "send_command") as mock_send_command,
    ):
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    mock_send_command.assert_called()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_set_percentage(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test set percentage."""
    mock_list_devices.return_value = [
        CIRCULATOR_FAN_INFO,
    ]
    mock_get_status.side_effect = [
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
        {"power": "off", "mode": "direct", "fanSpeed": "5"},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_ON

    with (
        patch.object(SwitchBotAPI, "send_command") as mock_send_command,
    ):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PERCENTAGE: 5},
            blocking=True,
        )
    mock_send_command.assert_called()


async def test_set_preset_mode(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test set preset mode."""
    mock_list_devices.return_value = [
        CIRCULATOR_FAN_INFO,
    ]
    mock_get_status.side_effect = [
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
        {"power": "on", "mode": "direct", "fanSpeed": "0"},
        {"power": "on", "mode": "baby", "fanSpeed": "0"},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "fan.battery_fan_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_ON

    with (
        patch.object(SwitchBotAPI, "send_command") as mock_send_command,
    ):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: "baby"},
            blocking=True,
        )
    mock_send_command.assert_called_once()


async def test_air_purifier(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_list_devices,
    mock_get_status,
) -> None:
    """Test air purifier."""

    mock_list_devices.return_value = [AIR_PURIFIER_INFO]
    mock_get_status.return_value = await async_load_json_object_fixture(
        hass, "air_purifier_status.json", DOMAIN
    )

    with patch("homeassistant.components.switchbot_cloud.PLATFORMS", [Platform.FAN]):
        entry = await configure_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.parametrize(
    ("service", "service_data", "expected_call_args"),
    [
        (
            "turn_on",
            {},
            (
                "air-purifier-id-1",
                switchbot_api.CommonCommands.ON,
                "command",
                "default",
            ),
        ),
        (
            "turn_off",
            {},
            (
                "air-purifier-id-1",
                switchbot_api.CommonCommands.OFF,
                "command",
                "default",
            ),
        ),
        (
            "set_preset_mode",
            {"preset_mode": "sleep"},
            (
                "air-purifier-id-1",
                switchbot_api.AirPurifierCommands.SET_MODE,
                "command",
                {"mode": 3},
            ),
        ),
    ],
)
async def test_air_purifier_controller(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    service: str,
    service_data: dict,
    expected_call_args: tuple,
) -> None:
    """Test controlling the air purifier with mocked delay."""
    mock_list_devices.return_value = [AIR_PURIFIER_INFO]
    mock_get_status.return_value = {"power": "OFF", "mode": 2}

    await configure_integration(hass)
    fan_id = "fan.air_purifier_1"

    with (
        patch.object(SwitchBotAPI, "send_command") as mocked_send_command,
    ):
        await hass.services.async_call(
            FAN_DOMAIN,
            service,
            {**service_data, ATTR_ENTITY_ID: fan_id},
            blocking=True,
        )

        mocked_send_command.assert_awaited_once_with(*expected_call_args)
