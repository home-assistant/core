"""Tests for the switchbot select platform."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import DOMAIN, WOMETERTHPC_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


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
        await hass.async_block_till_done()

        state = hass.states.get("select.test_name_time_format")
        assert state is not None
        assert state.state == expected_state


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
        await hass.async_block_till_done()

        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.test_name_time_format",
                ATTR_OPTION: expected_state,
            },
            blocking=True,
        )

        mock_set_time_display_format.assert_awaited_once_with(origin_mode)

        state = hass.states.get("select.test_name_time_format")
        assert state is not None
        assert state.state == expected_state
