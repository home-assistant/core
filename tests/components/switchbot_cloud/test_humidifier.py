"""Test for the switchbot_cloud humidifiers."""

from unittest.mock import patch

import pytest
import switchbot_api
from switchbot_api import Device
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.humidifier import DOMAIN as HUMIDIFIER_DOMAIN
from homeassistant.components.switchbot_cloud import SwitchBotAPI
from homeassistant.components.switchbot_cloud.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import HUMIDIFIER2_INFO, HUMIDIFIER_INFO, configure_integration

from tests.common import async_load_json_array_fixture, snapshot_platform


@pytest.mark.parametrize(
    ("device_info", "index"),
    [
        (HUMIDIFIER_INFO, 6),
        (HUMIDIFIER2_INFO, 7),
    ],
)
async def test_humidifier(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_list_devices,
    mock_get_status,
    device_info: Device,
    index: int,
) -> None:
    """Test humidifier sensors."""

    mock_list_devices.return_value = [device_info]
    json_data = await async_load_json_array_fixture(hass, "status.json", DOMAIN)
    mock_get_status.return_value = json_data[index]

    with patch(
        "homeassistant.components.switchbot_cloud.PLATFORMS", [Platform.HUMIDIFIER]
    ):
        entry = await configure_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.parametrize(
    ("service", "service_data", "expected_call_args"),
    [
        (
            "turn_on",
            {},
            (
                "humidifier-id-1",
                switchbot_api.CommonCommands.ON,
                "command",
                "default",
            ),
        ),
        (
            "turn_off",
            {},
            (
                "humidifier-id-1",
                switchbot_api.CommonCommands.OFF,
                "command",
                "default",
            ),
        ),
        (
            "set_humidity",
            {"humidity": 15},
            (
                "humidifier-id-1",
                switchbot_api.HumidifierCommands.SET_MODE,
                "command",
                "101",
            ),
        ),
        (
            "set_humidity",
            {"humidity": 60},
            (
                "humidifier-id-1",
                switchbot_api.HumidifierCommands.SET_MODE,
                "command",
                "102",
            ),
        ),
        (
            "set_humidity",
            {"humidity": 80},
            (
                "humidifier-id-1",
                switchbot_api.HumidifierCommands.SET_MODE,
                "command",
                "103",
            ),
        ),
        (
            "set_mode",
            {"mode": "auto"},
            (
                "humidifier-id-1",
                switchbot_api.HumidifierCommands.SET_MODE,
                "command",
                "auto",
            ),
        ),
        (
            "set_mode",
            {"mode": "normal"},
            (
                "humidifier-id-1",
                switchbot_api.HumidifierCommands.SET_MODE,
                "command",
                "102",
            ),
        ),
    ],
)
async def test_humidifier_controller(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    service: str,
    service_data: dict,
    expected_call_args: tuple,
) -> None:
    """Test controlling the humidifier with mocked delay."""
    mock_list_devices.return_value = [HUMIDIFIER_INFO]
    mock_get_status.return_value = {"power": "OFF", "mode": 2}

    await configure_integration(hass)
    humidifier_id = "humidifier.humidifier_1"

    with patch.object(SwitchBotAPI, "send_command") as mocked_send_command:
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            service,
            {**service_data, ATTR_ENTITY_ID: humidifier_id},
            blocking=True,
        )

        mocked_send_command.assert_awaited_once_with(*expected_call_args)


@pytest.mark.parametrize(
    ("service", "service_data", "expected_call_args"),
    [
        (
            "turn_on",
            {},
            (
                "humidifier2-id-1",
                switchbot_api.CommonCommands.ON,
                "command",
                "default",
            ),
        ),
        (
            "turn_off",
            {},
            (
                "humidifier2-id-1",
                switchbot_api.CommonCommands.OFF,
                "command",
                "default",
            ),
        ),
        (
            "set_humidity",
            {"humidity": 50},
            (
                "humidifier2-id-1",
                switchbot_api.HumidifierV2Commands.SET_MODE,
                "command",
                {"mode": 2, "humidity": 50},
            ),
        ),
        (
            "set_mode",
            {"mode": "auto"},
            (
                "humidifier2-id-1",
                switchbot_api.HumidifierV2Commands.SET_MODE,
                "command",
                {"mode": 7},
            ),
        ),
    ],
)
async def test_humidifier2_controller(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    service: str,
    service_data: dict,
    expected_call_args: tuple,
) -> None:
    """Test controlling the humidifier2 with mocked delay."""
    mock_list_devices.return_value = [HUMIDIFIER2_INFO]
    mock_get_status.return_value = {"power": "off", "mode": 2}

    await configure_integration(hass)
    humidifier_id = "humidifier.humidifier2_1"

    with patch.object(SwitchBotAPI, "send_command") as mocked_send_command:
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            service,
            {**service_data, ATTR_ENTITY_ID: humidifier_id},
            blocking=True,
        )

        mocked_send_command.assert_awaited_once_with(*expected_call_args)
