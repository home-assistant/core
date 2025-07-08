"""Test the switchbot fan."""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from switchbot import SwitchbotModel
from switchbot.devices.device import SwitchbotOperationError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.fan import (
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_OSCILLATE,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import (
    AIR_PURIFIER_PM25_SERVICE_INFO,
    AIR_PURIFIER_TABLE_VOC_SERVICE_INFO,
    AIR_PURIFIER_TBALE_PM25_SERVICE_INFO,
    AIR_PURIFIER_VOC_SERVICE_INFO,
    setup_integration,
    snapshot_switchbot_entities,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    switchbot_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Switchbot entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_switchbot_entities(hass, entity_registry, snapshot, Platform.FAN)


@pytest.mark.parametrize("switchbot_model", [SwitchbotModel.CIRCULATOR_FAN])
@pytest.mark.parametrize(
    ("service", "extra_service_data", "method", "args"),
    [
        (
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: "baby"},
            "set_preset_mode",
            ["baby"],
        ),
        (SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: 50}, "set_percentage", [50]),
        (SERVICE_OSCILLATE, {ATTR_OSCILLATING: True}, "set_oscillation", [True]),
        (SERVICE_OSCILLATE, {ATTR_OSCILLATING: False}, "set_oscillation", [False]),
        (
            SERVICE_TURN_ON,
            {},
            "turn_on",
            [],
        ),
        (
            SERVICE_TURN_OFF,
            {},
            "turn_off",
            [],
        ),
    ],
)
async def test_circulator_fan_controlling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_switchbot_circulator_fan: dict[str, AsyncMock],
    service: str,
    extra_service_data: dict[str, Any],
    method: str,
    args: list[Any],
) -> None:
    """Test Circulator fan controlling."""

    await setup_integration(hass, mock_config_entry)
    entity_id = "fan.test_name"

    await hass.services.async_call(
        FAN_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id} | extra_service_data,
        blocking=True,
    )
    mock_switchbot_circulator_fan[method].assert_awaited_once_with(*args)


@pytest.mark.parametrize(
    "switchbot_model", [SwitchbotModel.AIR_PURIFIER_TABLE, SwitchbotModel.AIR_PURIFIER]
)
@pytest.mark.parametrize(
    ("service", "extra_service_data", "method", "args"),
    [
        (
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: "baby"},
            "set_preset_mode",
            ["baby"],
        ),
        (SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: 50}, "set_percentage", [50]),
        (SERVICE_OSCILLATE, {ATTR_OSCILLATING: True}, "set_oscillation", [True]),
        (SERVICE_OSCILLATE, {ATTR_OSCILLATING: False}, "set_oscillation", [False]),
        (SERVICE_TURN_ON, {}, "turn_on", []),
        (SERVICE_TURN_OFF, {}, "turn_off", []),
    ],
)
async def test_air_purifier_controlling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_switchbot_air_purifier: dict[str, AsyncMock],
    service: str,
    extra_service_data: dict[str, Any],
    method: str,
    args: list[Any],
) -> None:
    """Test Air purifier controlling."""

    await setup_integration(hass, mock_config_entry)
    entity_id = "fan.test_name"

    await hass.services.async_call(
        FAN_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id} | extra_service_data,
        blocking=True,
    )
    mock_switchbot_air_purifier[method].assert_awaited_once_with(*args)


# @pytest.mark.parametrize(
#     ("service_info", "sensor_type"),
#     [
#         (AIR_PURIFIER_VOC_SERVICE_INFO, "air_purifier"),
#         (AIR_PURIFIER_TABLE_VOC_SERVICE_INFO, "air_purifier_table"),
#         (AIR_PURIFIER_PM25_SERVICE_INFO, "air_purifier"),
#         (AIR_PURIFIER_TBALE_PM25_SERVICE_INFO, "air_purifier_table"),
#     ],
# )
# @pytest.mark.parametrize(
#     ("service", "service_data", "mock_method"),
#     [
#         (
#             SERVICE_SET_PRESET_MODE,
#             {ATTR_PRESET_MODE: "sleep"},
#             "set_preset_mode",
#         ),
#         (
#             SERVICE_TURN_OFF,
#             {},
#             "turn_off",
#         ),
#         (
#             SERVICE_TURN_ON,
#             {},
#             "turn_on",
#         ),
#     ],
# )
# async def test_air_purifier_controlling(
#     hass: HomeAssistant,
#     mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
#     service_info: BluetoothServiceInfoBleak,
#     sensor_type: str,
#     service: str,
#     service_data: dict,
#     mock_method: str,
# ) -> None:
#     """Test controlling the air purifier with different services."""
#     inject_bluetooth_service_info(hass, service_info)
#
#     entry = mock_entry_encrypted_factory(sensor_type)
#     entity_id = "fan.test_name"
#     entry.add_to_hass(hass)
#
#     mocked_instance = AsyncMock(return_value=True)
#     mcoked_none_instance = AsyncMock(return_value=None)
#     with patch.multiple(
#         "homeassistant.components.switchbot.fan.switchbot.SwitchbotAirPurifier",
#         get_basic_info=mcoked_none_instance,
#         update=mcoked_none_instance,
#         **{mock_method: mocked_instance},
#     ):
#         assert await hass.config_entries.async_setup(entry.entry_id)
#         await hass.async_block_till_done()
#
#         await hass.services.async_call(
#             FAN_DOMAIN,
#             service,
#             {**service_data, ATTR_ENTITY_ID: entity_id},
#             blocking=True,
#         )
#
#         mocked_instance.assert_awaited_once()


@pytest.mark.parametrize(
    ("service_info", "sensor_type"),
    [
        (AIR_PURIFIER_VOC_SERVICE_INFO, "air_purifier"),
        (AIR_PURIFIER_TABLE_VOC_SERVICE_INFO, "air_purifier_table"),
        (AIR_PURIFIER_PM25_SERVICE_INFO, "air_purifier"),
        (AIR_PURIFIER_TBALE_PM25_SERVICE_INFO, "air_purifier_table"),
    ],
)
@pytest.mark.parametrize(
    ("service", "service_data", "mock_method"),
    [
        (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: "sleep"}, "set_preset_mode"),
        (SERVICE_TURN_OFF, {}, "turn_off"),
        (SERVICE_TURN_ON, {}, "turn_on"),
    ],
)
@pytest.mark.parametrize(
    ("exception", "error_message"),
    [
        (
            SwitchbotOperationError("Operation failed"),
            "An error occurred while performing the action: Operation failed",
        ),
    ],
)
async def test_exception_handling_air_purifier_service(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    service_info: BluetoothServiceInfoBleak,
    sensor_type: str,
    service: str,
    service_data: dict,
    mock_method: str,
    exception: Exception,
    error_message: str,
) -> None:
    """Test exception handling for air purifier service with exception."""
    inject_bluetooth_service_info(hass, service_info)

    entry = mock_entry_encrypted_factory(sensor_type)
    entry.add_to_hass(hass)
    entity_id = "fan.test_name"

    mcoked_none_instance = AsyncMock(return_value=None)
    with patch.multiple(
        "homeassistant.components.switchbot.fan.switchbot.SwitchbotAirPurifier",
        get_basic_info=mcoked_none_instance,
        update=mcoked_none_instance,
        **{mock_method: AsyncMock(side_effect=exception)},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match=error_message):
            await hass.services.async_call(
                FAN_DOMAIN,
                service,
                {**service_data, ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )
