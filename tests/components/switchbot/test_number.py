"""Tests for the switchbot number platform."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

from bleak_retry_connector import BleakConnectionError
import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_UNKNOWN,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import ServiceValidationError
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

TIME_OFFSET_ENTITY_ID = "number.test_name_display_time_offset"


@pytest.mark.parametrize(
    ("offset_seconds_on_device", "expected_state"),
    [
        (0, 0),
        (60, 1),
        (-60, -1),
        (3600, 60),
        (-3600, -60),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_meter_pro_co2_display_time_offset_initial_state(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    offset_seconds_on_device: int,
    expected_state: int,
) -> None:
    """Test display_time_offset gets initial state from MeterProCO2."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOMETERTHPC_SERVICE_INFO)

    entry = mock_entry_factory("hygrometer_co2")
    entry.add_to_hass(hass)

    with patch(
        "switchbot.SwitchbotMeterProCO2.get_time_offset",
        return_value=offset_seconds_on_device,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get(TIME_OFFSET_ENTITY_ID)
        assert state is not None
        assert float(state.state) == expected_state


async def test_meter_pro_co2_display_time_offset_disabled_by_default(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test the offset entity does not connect while it is disabled."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOMETERTHPC_SERVICE_INFO)

    entry = mock_entry_factory("hygrometer_co2")
    entry.add_to_hass(hass)

    mock_get_time_offset = AsyncMock(return_value=60)
    with patch("switchbot.SwitchbotMeterProCO2.get_time_offset", mock_get_time_offset):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_get_time_offset.assert_not_awaited()
    assert hass.states.get(TIME_OFFSET_ENTITY_ID) is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_meter_pro_co2_display_time_offset_waits_for_start(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test the offset is only read once Home Assistant has started."""
    hass.set_state(CoreState.not_running)
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOMETERTHPC_SERVICE_INFO)

    entry = mock_entry_factory("hygrometer_co2")
    entry.add_to_hass(hass)

    mock_get_time_offset = AsyncMock(return_value=60)
    with patch("switchbot.SwitchbotMeterProCO2.get_time_offset", mock_get_time_offset):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        # Setting up the platform must not reach out over Bluetooth.
        mock_get_time_offset.assert_not_awaited()
        assert hass.states.get(TIME_OFFSET_ENTITY_ID).state == STATE_UNKNOWN

        hass.set_state(CoreState.running)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert mock_get_time_offset.await_count
        assert hass.states.get(TIME_OFFSET_ENTITY_ID).state == "1"


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
async def test_meter_pro_co2_display_time_offset_unreachable(
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

    mock_get_time_offset = AsyncMock(return_value=60, side_effect=side_effect)
    with patch("switchbot.SwitchbotMeterProCO2.get_time_offset", mock_get_time_offset):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_get_time_offset.await_count == expected_await_count
    assert hass.states.get(TIME_OFFSET_ENTITY_ID).state == STATE_UNKNOWN
    assert "Error on device update" not in caplog.text


@pytest.mark.parametrize(
    ("time_offset", "expected_seconds_on_device"),
    [
        (0, 0),
        (1, 60),
        (-1, -60),
        (5, 300),
        (-5, -300),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_meter_pro_co2_set_display_time_offset(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    time_offset: int,
    expected_seconds_on_device: int,
) -> None:
    """Test setting time offset on a MeterProCO2 device."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOMETERTHPC_SERVICE_INFO)

    entry = mock_entry_factory("hygrometer_co2")
    entry.add_to_hass(hass)

    mock_get_time_offset = AsyncMock(return_value=60)
    mock_set_time_offset = AsyncMock(return_value=True)

    with (
        patch(
            "switchbot.SwitchbotMeterProCO2.get_time_offset",
            mock_get_time_offset,
        ),
        patch(
            "switchbot.SwitchbotMeterProCO2.set_time_offset",
            mock_set_time_offset,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: TIME_OFFSET_ENTITY_ID,
                ATTR_VALUE: time_offset,
            },
            blocking=True,
        )

        mock_set_time_offset.assert_awaited_once_with(expected_seconds_on_device)

        state = hass.states.get(TIME_OFFSET_ENTITY_ID)
        assert state is not None
        assert float(state.state) == time_offset


@pytest.mark.parametrize(
    ("value"),
    [
        (300000),
        (-300000),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_display_time_offset_out_of_range(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    value: int,
) -> None:
    """Test setting time offset with out-of-range values."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOMETERTHPC_SERVICE_INFO)

    entry = mock_entry_factory("hygrometer_co2")
    entry.add_to_hass(hass)

    mock_get_time_offset = AsyncMock(return_value=0)
    mock_set_time_offset = AsyncMock(return_value=True)

    with (
        patch(
            "switchbot.SwitchbotMeterProCO2.get_time_offset",
            mock_get_time_offset,
        ),
        patch(
            "switchbot.SwitchbotMeterProCO2.set_time_offset",
            mock_set_time_offset,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        with pytest.raises(
            ServiceValidationError,
            match=(
                r"Value -?\d+\.0 for"
                r" number\.test_name_display_time_offset"
                r" is outside valid range"
            ),
        ):
            await hass.services.async_call(
                NUMBER_DOMAIN,
                SERVICE_SET_VALUE,
                {
                    ATTR_ENTITY_ID: TIME_OFFSET_ENTITY_ID,
                    ATTR_VALUE: value,
                },
                blocking=True,
            )

        mock_set_time_offset.assert_not_awaited()


@pytest.mark.parametrize(
    ("entity_id", "set_method"),
    [
        (
            "number.test_name_horizontal_oscillation_angle",
            "set_horizontal_oscillation_angle",
        ),
        (
            "number.test_name_vertical_oscillation_angle",
            "set_vertical_oscillation_angle",
        ),
    ],
)
async def test_standing_fan_oscillation_angle_number(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    entity_id: str,
    set_method: str,
) -> None:
    """Test horizontal/vertical oscillation angle number entities."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, STANDING_FAN_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="standing_fan")
    entry.add_to_hass(hass)

    mocked_set = AsyncMock(return_value=True)
    with patch.multiple(
        "homeassistant.components.switchbot.number.switchbot.SwitchbotStandingFan",
        get_basic_info=AsyncMock(return_value=None),
        **{set_method: mocked_set},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 60},
            blocking=True,
        )

        mocked_set.assert_awaited_once_with(60)

        state = hass.states.get(entity_id)
        assert state is not None
        assert float(state.state) == 60
