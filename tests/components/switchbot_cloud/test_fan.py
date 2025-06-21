"""Test for the switchbot_cloud air purifiers."""

from unittest.mock import AsyncMock, patch

import pytest
import switchbot_api
from switchbot_api import Device
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.switchbot_cloud import SwitchBotAPI
from homeassistant.components.switchbot_cloud.const import DEFAULT_DELAY_TIME, DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import configure_integration

from tests.common import async_load_json_object_fixture, snapshot_platform

AIR_PURIFIER_INFO = Device(
    version="V1.0",
    deviceId="air-purifier-id-1",
    deviceName="air-purifier-1",
    deviceType="Air Purifier Table PM2.5",
    hubDeviceId="test-hub-id",
)


async def test_air_purifier(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_list_devices,
    mock_get_status,
) -> None:
    """Test air purifier sensors."""

    mock_list_devices.return_value = [AIR_PURIFIER_INFO]
    mock_get_status.return_value = await async_load_json_object_fixture(
        hass, "air_purifier_status.json", DOMAIN
    )

    with patch("homeassistant.components.switchbot_cloud.PLATFORMS", [Platform.FAN]):
        entry = await configure_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_air_purifier_no_coordinator_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_list_devices,
    mock_get_status,
) -> None:
    """Test air purifier sensors are unknown without coordinator data."""
    mock_list_devices.return_value = [AIR_PURIFIER_INFO]
    mock_get_status.return_value = None

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
        patch("asyncio.sleep", AsyncMock()) as mocked_sleep,
    ):
        await hass.services.async_call(
            FAN_DOMAIN,
            service,
            {**service_data, ATTR_ENTITY_ID: fan_id},
            blocking=True,
        )

        mocked_send_command.assert_awaited_once_with(*expected_call_args)
        mocked_sleep.assert_awaited_once_with(DEFAULT_DELAY_TIME)
