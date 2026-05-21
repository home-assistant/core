"""Tests for the switchbot number platform."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from . import DOMAIN, WOMETERTHPC_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


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
        await hass.async_block_till_done()

        state = hass.states.get("number.test_name_display_time_offset")
        assert state is not None
        assert float(state.state) == expected_state


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
        await hass.async_block_till_done()

        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.test_name_display_time_offset",
                ATTR_VALUE: time_offset,
            },
            blocking=True,
        )

        mock_set_time_offset.assert_awaited_once_with(expected_seconds_on_device)

        state = hass.states.get("number.test_name_display_time_offset")
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
        await hass.async_block_till_done()

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
                    ATTR_ENTITY_ID: "number.test_name_display_time_offset",
                    ATTR_VALUE: value,
                },
                blocking=True,
            )

        mock_set_time_offset.assert_not_awaited()
