"""Test the switchbot fan."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

import pytest
from switchbot import SwitchbotOperationError

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
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import (
    AIR_PURIFIER_JP_SERVICE_INFO,
    AIR_PURIFIER_TABLE_JP_SERVICE_INFO,
    AIR_PURIFIER_TABLE_US_SERVICE_INFO,
    AIR_PURIFIER_US_SERVICE_INFO,
    CIRCULATOR_FAN_SERVICE_INFO,
    STANDING_FAN_SERVICE_INFO,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.parametrize(
    (
        "service",
        "service_data",
        "mock_method",
    ),
    [
        (
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: "baby"},
            "set_preset_mode",
        ),
        (
            SERVICE_SET_PERCENTAGE,
            {ATTR_PERCENTAGE: 27},
            "set_percentage",
        ),
        (
            SERVICE_OSCILLATE,
            {ATTR_OSCILLATING: True},
            "set_oscillation",
        ),
        (
            SERVICE_TURN_OFF,
            {},
            "turn_off",
        ),
        (
            SERVICE_TURN_ON,
            {},
            "turn_on",
        ),
    ],
)
async def test_circulator_fan_controlling(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    service: str,
    service_data: dict,
    mock_method: str,
) -> None:
    """Test controlling the circulator fan with different services."""
    inject_bluetooth_service_info(hass, CIRCULATOR_FAN_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="circulator_fan")
    entity_id = "fan.test_name"
    entry.add_to_hass(hass)

    mocked_instance = AsyncMock(return_value=True)
    mcoked_none_instance = AsyncMock(return_value=None)
    with patch.multiple(
        "homeassistant.components.switchbot.fan.switchbot.SwitchbotFan",
        get_basic_info=mcoked_none_instance,
        **{mock_method: mocked_instance},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            FAN_DOMAIN,
            service,
            {**service_data, ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        mocked_instance.assert_awaited_once()


@pytest.mark.parametrize(
    ("service_info", "sensor_type"),
    [
        (AIR_PURIFIER_JP_SERVICE_INFO, "air_purifier_jp"),
        (AIR_PURIFIER_TABLE_JP_SERVICE_INFO, "air_purifier_table_jp"),
        (AIR_PURIFIER_US_SERVICE_INFO, "air_purifier_us"),
        (AIR_PURIFIER_TABLE_US_SERVICE_INFO, "air_purifier_table_us"),
    ],
)
@pytest.mark.parametrize(
    ("service", "service_data", "mock_method"),
    [
        (
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: "sleep"},
            "set_preset_mode",
        ),
        (
            SERVICE_SET_PERCENTAGE,
            {ATTR_PERCENTAGE: 27},
            "set_percentage",
        ),
        (
            SERVICE_TURN_OFF,
            {},
            "turn_off",
        ),
        (
            SERVICE_TURN_ON,
            {},
            "turn_on",
        ),
    ],
)
async def test_air_purifier_controlling(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    service_info: BluetoothServiceInfoBleak,
    sensor_type: str,
    service: str,
    service_data: dict,
    mock_method: str,
) -> None:
    """Test controlling the air purifier with different services."""
    inject_bluetooth_service_info(hass, service_info)

    entry = mock_entry_encrypted_factory(sensor_type)
    entity_id = "fan.test_name"
    entry.add_to_hass(hass)

    mocked_instance = AsyncMock(return_value=True)
    mcoked_none_instance = AsyncMock(return_value=None)
    with patch.multiple(
        "homeassistant.components.switchbot.fan.switchbot.SwitchbotAirPurifier",
        get_basic_info=mcoked_none_instance,
        update=mcoked_none_instance,
        **{mock_method: mocked_instance},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            FAN_DOMAIN,
            service,
            {**service_data, ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        mocked_instance.assert_awaited_once()


@pytest.mark.parametrize(
    ("service_info", "sensor_type"),
    [
        (AIR_PURIFIER_JP_SERVICE_INFO, "air_purifier_jp"),
        (AIR_PURIFIER_TABLE_JP_SERVICE_INFO, "air_purifier_table_jp"),
        (AIR_PURIFIER_US_SERVICE_INFO, "air_purifier_us"),
        (AIR_PURIFIER_TABLE_US_SERVICE_INFO, "air_purifier_table_us"),
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


@pytest.mark.parametrize(
    ("service", "service_data", "mock_method", "expected_call"),
    [
        (
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: "sleep"},
            "set_preset_mode",
            ("sleep",),
        ),
        (SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: 50}, "set_percentage", (50,)),
        (SERVICE_OSCILLATE, {ATTR_OSCILLATING: True}, "set_oscillation", (True,)),
        (SERVICE_TURN_OFF, {}, "turn_off", ()),
        (SERVICE_TURN_ON, {}, "turn_on", ()),
    ],
)
async def test_standing_fan_controlling(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    service: str,
    service_data: dict,
    mock_method: str,
    expected_call: tuple,
) -> None:
    """Test controlling the standing fan with different services."""
    inject_bluetooth_service_info(hass, STANDING_FAN_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="standing_fan")
    entity_id = "fan.test_name"
    entry.add_to_hass(hass)

    mocked_instance = AsyncMock(return_value=True)
    mocked_none = AsyncMock(return_value=None)
    with patch.multiple(
        "homeassistant.components.switchbot.fan.switchbot.SwitchbotStandingFan",
        get_basic_info=mocked_none,
        **{mock_method: mocked_instance},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            FAN_DOMAIN,
            service,
            {**service_data, ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        mocked_instance.assert_awaited_once_with(*expected_call)


@pytest.mark.parametrize(
    ("service", "service_data", "mock_method"),
    [
        (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: "sleep"}, "set_preset_mode"),
        (SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: 50}, "set_percentage"),
        (SERVICE_OSCILLATE, {ATTR_OSCILLATING: True}, "set_oscillation"),
        (SERVICE_TURN_OFF, {}, "turn_off"),
        (SERVICE_TURN_ON, {}, "turn_on"),
    ],
)
async def test_exception_handling_standing_fan_service(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    service: str,
    service_data: dict,
    mock_method: str,
) -> None:
    """Test a communication error raises HomeAssistantError for the standing fan."""
    inject_bluetooth_service_info(hass, STANDING_FAN_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="standing_fan")
    entry.add_to_hass(hass)
    entity_id = "fan.test_name"

    mocked_none = AsyncMock(return_value=None)
    with patch.multiple(
        "homeassistant.components.switchbot.fan.switchbot.SwitchbotStandingFan",
        get_basic_info=mocked_none,
        **{
            mock_method: AsyncMock(
                side_effect=SwitchbotOperationError("Operation failed")
            )
        },
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(
            HomeAssistantError,
            match="An error occurred while performing the action: Operation failed",
        ):
            await hass.services.async_call(
                FAN_DOMAIN,
                service,
                {**service_data, ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )


@pytest.mark.parametrize(
    ("service", "service_data", "mock_method"),
    [
        (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: "sleep"}, "set_preset_mode"),
        (SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: 50}, "set_percentage"),
        (SERVICE_OSCILLATE, {ATTR_OSCILLATING: True}, "set_oscillation"),
        (SERVICE_TURN_OFF, {}, "turn_off"),
        (SERVICE_TURN_ON, {}, "turn_on"),
    ],
)
async def test_standing_fan_command_failure(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    service: str,
    service_data: dict,
    mock_method: str,
) -> None:
    """Test an unsuccessful command (device returns False) raises HomeAssistantError."""
    inject_bluetooth_service_info(hass, STANDING_FAN_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="standing_fan")
    entry.add_to_hass(hass)
    entity_id = "fan.test_name"

    mocked_none = AsyncMock(return_value=None)
    with patch.multiple(
        "homeassistant.components.switchbot.fan.switchbot.SwitchbotStandingFan",
        get_basic_info=mocked_none,
        **{mock_method: AsyncMock(return_value=False)},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(
            HomeAssistantError, match="Failed to send the command to the fan"
        ):
            await hass.services.async_call(
                FAN_DOMAIN,
                service,
                {**service_data, ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )
