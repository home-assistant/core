"""Tests for the switchbot select platform."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

from bleak_retry_connector import BleakConnectionError
import pytest
from switchbot import NightLightState

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_UNKNOWN,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.setup import async_setup_component

from . import (
    DOMAIN,
    STANDING_FAN_SERVICE_INFO,
    WOMETERTHPC_SERVICE_INFO,
    WOMETERTHPC_SERVICE_INFO_NOT_CONNECTABLE,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    inject_bluetooth_service_info_bleak,
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

    entry = mock_entry_factory("hygrometer_co2")
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

    entry = mock_entry_factory("hygrometer_co2")
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

    entry = mock_entry_factory("hygrometer_co2")
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

    entry = mock_entry_factory("hygrometer_co2")
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

    entry = mock_entry_factory("hygrometer_co2")
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
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: TIME_FORMAT_ENTITY_ID,
                ATTR_OPTION: expected_state,
            },
            blocking=True,
        )

        mock_set_time_display_format.assert_awaited_once_with(origin_mode)

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
        await hass.async_block_till_done()

        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: "select.test_name_night_light", ATTR_OPTION: option},
            blocking=True,
        )

        mocked_set.assert_awaited_once_with(expected_state)
