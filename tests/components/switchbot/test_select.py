"""Tests for the switchbot select platform."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from bleak_retry_connector import BleakConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.bluetooth import (
    inject_bluetooth_service_info,
    inject_bluetooth_service_info_bleak,
)
from switchbot import NightLightState, QuickKeyFunction

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SelectService,
    SelectServiceArgument,
)
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    STATE_UNKNOWN,
    CommonServiceArgument,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import (
    DOMAIN,
    LOCK_ULTRA_QUICK_KEY_SETTINGS,
    LOCK_ULTRA_SERVICE_INFO,
    STANDING_FAN_SERVICE_INFO,
    WOMETERTHPC_SERVICE_INFO,
    WOMETERTHPC_SERVICE_INFO_NOT_CONNECTABLE,
    patch_lock_ultra_quick_key,
)

TIME_FORMAT_ENTITY_ID = "select.test_name_time_format"
DEVICE_DATETIME_24H = {
    "12h_mode": False,
    "year": 2025,
    "month": 1,
    "day": 9,
    "hour": 12,
    "minute": 0,
    "second": 0,
}


@pytest.mark.parametrize(
    ("mode", "expected_state"),
    [
        (False, "24h"),
        (True, "12h"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_time_format_select_initial_state(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    mode: bool,
    expected_state: str,
) -> None:
    """Test the time format select entity initial state."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOMETERTHPC_SERVICE_INFO)

    entry = mock_entry_factory("meter_pro_co2")
    entry.add_to_hass(hass)

    with patch(
        "switchbot.SwitchbotMeterProCO2.get_datetime",
        return_value={
            "12h_mode": mode,
            "year": 2025,
            "month": 1,
            "day": 9,
            "hour": 12,
            "minute": 0,
            "second": 0,
        },
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get(TIME_FORMAT_ENTITY_ID)
        assert state is not None
        assert state.state == expected_state


async def test_time_format_select_disabled_by_default(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test the time format entity does not connect while it is disabled."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOMETERTHPC_SERVICE_INFO)

    entry = mock_entry_factory("meter_pro_co2")
    entry.add_to_hass(hass)

    mock_get_datetime = AsyncMock(return_value=DEVICE_DATETIME_24H)
    with patch("switchbot.SwitchbotMeterProCO2.get_datetime", mock_get_datetime):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_get_datetime.assert_not_awaited()
    assert hass.states.get(TIME_FORMAT_ENTITY_ID) is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_time_format_select_waits_for_start(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test the time format is only read once Home Assistant has started."""
    hass.set_state(CoreState.not_running)
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOMETERTHPC_SERVICE_INFO)

    entry = mock_entry_factory("meter_pro_co2")
    entry.add_to_hass(hass)

    mock_get_datetime = AsyncMock(return_value=DEVICE_DATETIME_24H)
    with patch("switchbot.SwitchbotMeterProCO2.get_datetime", mock_get_datetime):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        # Setting up the platform must not reach out over Bluetooth.
        mock_get_datetime.assert_not_awaited()
        assert hass.states.get(TIME_FORMAT_ENTITY_ID).state == STATE_UNKNOWN

        hass.set_state(CoreState.running)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert mock_get_datetime.await_count
        assert hass.states.get(TIME_FORMAT_ENTITY_ID).state == "24h"


@pytest.mark.parametrize(
    ("service_info", "side_effect", "expected_await_count"),
    [
        pytest.param(
            WOMETERTHPC_SERVICE_INFO_NOT_CONNECTABLE,
            None,
            0,
            id="no_connectable_path",
        ),
        pytest.param(
            WOMETERTHPC_SERVICE_INFO,
            BleakConnectionError("no connectable Bluetooth adapters"),
            1,
            id="connection_fails",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_time_format_select_unreachable(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    caplog: pytest.LogCaptureFixture,
    service_info: BluetoothServiceInfoBleak,
    side_effect: Exception | None,
    expected_await_count: int,
) -> None:
    """Test an unreachable device leaves the entity added and unknown."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info_bleak(hass, service_info)

    entry = mock_entry_factory("meter_pro_co2")
    entry.add_to_hass(hass)

    mock_get_datetime = AsyncMock(
        return_value=DEVICE_DATETIME_24H, side_effect=side_effect
    )
    with patch("switchbot.SwitchbotMeterProCO2.get_datetime", mock_get_datetime):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_get_datetime.await_count == expected_await_count
    assert hass.states.get(TIME_FORMAT_ENTITY_ID).state == STATE_UNKNOWN
    assert "Error on device update" not in caplog.text


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_time_format_select_recovers_on_next_poll(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test a failed first read of the time format is retried on the next poll."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOMETERTHPC_SERVICE_INFO)

    entry = mock_entry_factory("meter_pro_co2")
    entry.add_to_hass(hass)

    mock_get_datetime = AsyncMock(
        side_effect=[
            BleakConnectionError("no connectable Bluetooth adapters"),
            DEVICE_DATETIME_24H,
        ]
    )
    with (
        patch("switchbot.SwitchbotMeterProCO2.get_datetime", mock_get_datetime),
        patch(
            "homeassistant.components.switchbot.select.SCAN_INTERVAL",
            timedelta(minutes=1),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        mock_get_datetime.assert_awaited_once()
        assert hass.states.get(TIME_FORMAT_ENTITY_ID).state == STATE_UNKNOWN

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1))
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_get_datetime.await_count == 2
    assert hass.states.get(TIME_FORMAT_ENTITY_ID).state == "24h"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("origin_mode", "expected_state"),
    [
        (False, "24h"),
        (True, "12h"),
    ],
)
async def test_set_time_format(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    origin_mode: bool,
    expected_state: str,
) -> None:
    """Test changing time format to 12h."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOMETERTHPC_SERVICE_INFO)

    entry = mock_entry_factory("meter_pro_co2")
    entry.add_to_hass(hass)

    mock_get_datetime = AsyncMock(
        return_value={
            "12h_mode": origin_mode,
            "year": 2025,
            "month": 1,
            "day": 9,
            "hour": 12,
            "minute": 0,
            "second": 0,
        }
    )
    mock_set_time_display_format = AsyncMock(return_value=True)

    with (
        patch(
            "switchbot.SwitchbotMeterProCO2.get_datetime",
            mock_get_datetime,
        ),
        patch(
            "switchbot.SwitchbotMeterProCO2.set_time_display_format",
            mock_set_time_display_format,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        await hass.services.async_call(
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            {
                CommonServiceArgument.ENTITY_ID: TIME_FORMAT_ENTITY_ID,
                SelectServiceArgument.OPTION: expected_state,
            },
            blocking=True,
        )

        mock_set_time_display_format.assert_awaited_once_with(origin_mode)
        # The value is read back from the device after it has been set.
        assert mock_get_datetime.await_count == 2

        state = hass.states.get(TIME_FORMAT_ENTITY_ID)
        assert state is not None
        assert state.state == expected_state


@pytest.mark.parametrize(
    ("device_state", "option", "expected_state"),
    [
        (NightLightState.OFF.value, "bright", NightLightState.LEVEL_1),
        (NightLightState.LEVEL_1.value, "soft", NightLightState.LEVEL_2),
        (NightLightState.LEVEL_2.value, "off", NightLightState.OFF),
    ],
)
async def test_standing_fan_night_light_select(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    device_state: int,
    option: str,
    expected_state: NightLightState,
) -> None:
    """Test night light select translates options to device commands."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, STANDING_FAN_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="standing_fan")
    entry.add_to_hass(hass)

    mocked_set = AsyncMock(return_value=True)
    with patch.multiple(
        "homeassistant.components.switchbot.select.switchbot.SwitchbotStandingFan",
        get_basic_info=AsyncMock(return_value=None),
        get_night_light_state=lambda self: device_state,
        set_night_light=mocked_set,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        await hass.services.async_call(
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            {
                CommonServiceArgument.ENTITY_ID: "select.test_name_night_light",
                SelectServiceArgument.OPTION: option,
            },
            blocking=True,
        )

        mocked_set.assert_awaited_once_with(expected_state)


QUICK_KEY_FUNCTION_ENTITY_ID = "select.test_name_quick_key_function"
QUICK_KEY_TRIGGER_ENTITY_ID = "select.test_name_quick_key_trigger"


@pytest.mark.parametrize(
    ("settings", "function_state", "trigger_state"),
    [
        pytest.param(
            LOCK_ULTRA_QUICK_KEY_SETTINGS,
            "lock_and_unlock",
            "single_press",
            id="toggle",
        ),
        pytest.param(
            LOCK_ULTRA_QUICK_KEY_SETTINGS
            | {"function": QuickKeyFunction.UNLOCK_ONLY, "double_press": True},
            "unlock_only",
            "double_press",
            id="unlock_only_double_press",
        ),
        pytest.param(
            LOCK_ULTRA_QUICK_KEY_SETTINGS | {"function": None},
            STATE_UNKNOWN,
            "single_press",
            id="undefined_function",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_quick_key_selects_initial_state(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    settings: dict[str, Any],
    function_state: str,
    trigger_state: str,
) -> None:
    """Test the Quick Key selects show what the lock reports."""
    inject_bluetooth_service_info(hass, LOCK_ULTRA_SERVICE_INFO)
    entry = mock_entry_encrypted_factory("lock_ultra")
    entry.add_to_hass(hass)

    patcher, _ = patch_lock_ultra_quick_key(settings)
    with patcher:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(QUICK_KEY_FUNCTION_ENTITY_ID).state == function_state
    assert hass.states.get(QUICK_KEY_TRIGGER_ENTITY_ID).state == trigger_state


async def test_quick_key_selects_disabled_by_default(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test the Quick Key entities do not connect to the lock while disabled."""
    inject_bluetooth_service_info(hass, LOCK_ULTRA_SERVICE_INFO)
    entry = mock_entry_encrypted_factory("lock_ultra")
    entry.add_to_hass(hass)

    mock_get_quick_key = AsyncMock(return_value=LOCK_ULTRA_QUICK_KEY_SETTINGS)
    with patch.multiple(
        "switchbot.SwitchbotLockUltra",
        update=AsyncMock(return_value=None),
        get_quick_key=mock_get_quick_key,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_get_quick_key.assert_not_awaited()
    assert hass.states.get(QUICK_KEY_FUNCTION_ENTITY_ID) is None
    assert hass.states.get(QUICK_KEY_TRIGGER_ENTITY_ID) is None


@pytest.mark.parametrize(
    ("entity_id", "option", "expected_kwargs"),
    [
        pytest.param(
            QUICK_KEY_FUNCTION_ENTITY_ID,
            "unlock_only",
            {"function": QuickKeyFunction.UNLOCK_ONLY},
            id="function",
        ),
        pytest.param(
            QUICK_KEY_TRIGGER_ENTITY_ID,
            "double_press",
            {"double_press": True},
            id="trigger",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_quick_key_select_option(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    entity_id: str,
    option: str,
    expected_kwargs: dict[str, Any],
) -> None:
    """Test selecting a Quick Key option writes only that setting."""
    inject_bluetooth_service_info(hass, LOCK_ULTRA_SERVICE_INFO)
    entry = mock_entry_encrypted_factory("lock_ultra")
    entry.add_to_hass(hass)

    patcher, mock_set_quick_key = patch_lock_ultra_quick_key(
        LOCK_ULTRA_QUICK_KEY_SETTINGS
    )
    with patcher:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        await hass.services.async_call(
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            {
                CommonServiceArgument.ENTITY_ID: entity_id,
                SelectServiceArgument.OPTION: option,
            },
            blocking=True,
        )

    mock_set_quick_key.assert_awaited_once_with(**expected_kwargs)
    assert hass.states.get(entity_id).state == option


@pytest.mark.parametrize(
    ("entity_id", "option", "initial_state"),
    [
        pytest.param(
            QUICK_KEY_FUNCTION_ENTITY_ID, "lock_only", "lock_and_unlock", id="function"
        ),
        pytest.param(
            QUICK_KEY_TRIGGER_ENTITY_ID, "double_press", "single_press", id="trigger"
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_quick_key_select_option_not_applied(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    entity_id: str,
    option: str,
    initial_state: str,
) -> None:
    """Test a write the lock does not confirm raises and keeps the old state."""
    inject_bluetooth_service_info(hass, LOCK_ULTRA_SERVICE_INFO)
    entry = mock_entry_encrypted_factory("lock_ultra")
    entry.add_to_hass(hass)

    patcher, _ = patch_lock_ultra_quick_key(
        LOCK_ULTRA_QUICK_KEY_SETTINGS, write_result=False
    )
    with patcher:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                SELECT_DOMAIN,
                SelectService.SELECT_OPTION,
                {
                    CommonServiceArgument.ENTITY_ID: entity_id,
                    SelectServiceArgument.OPTION: option,
                },
                blocking=True,
            )

    assert exc_info.value.translation_key == "quick_key_not_applied"
    assert hass.states.get(entity_id).state == initial_state


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_quick_key_selects_unknown_without_answer(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test the Quick Key selects stay unknown when the lock rejects the read."""
    inject_bluetooth_service_info(hass, LOCK_ULTRA_SERVICE_INFO)
    entry = mock_entry_encrypted_factory("lock_ultra")
    entry.add_to_hass(hass)

    with patch.multiple(
        "switchbot.SwitchbotLockUltra",
        update=AsyncMock(return_value=None),
        get_quick_key=AsyncMock(return_value=None),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(QUICK_KEY_FUNCTION_ENTITY_ID).state == STATE_UNKNOWN
    assert hass.states.get(QUICK_KEY_TRIGGER_ENTITY_ID).state == STATE_UNKNOWN
