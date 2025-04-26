"""Test the switchbot lights."""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from switchbot import ColorMode as switchbotColorMode

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import WOSTRIP_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.parametrize(
    (
        "service",
        "service_data",
        "mock_method",
        "expected_args",
        "color_modes",
        "color_mode",
    ),
    [
        (
            SERVICE_TURN_OFF,
            {},
            "turn_off",
            (),
            {switchbotColorMode.RGB},
            switchbotColorMode.RGB,
        ),
        (
            SERVICE_TURN_ON,
            {},
            "turn_on",
            (),
            {switchbotColorMode.RGB},
            switchbotColorMode.RGB,
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_BRIGHTNESS: 128},
            "set_brightness",
            (round(128 / 255 * 100),),
            {switchbotColorMode.RGB},
            switchbotColorMode.RGB,
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_RGB_COLOR: (255, 0, 0)},
            "set_rgb",
            (round(255 / 255 * 100), 255, 0, 0),
            {switchbotColorMode.RGB},
            switchbotColorMode.RGB,
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_COLOR_TEMP_KELVIN: 4000},
            "set_color_temp",
            (100, 4000),
            {switchbotColorMode.COLOR_TEMP},
            switchbotColorMode.COLOR_TEMP,
        ),
    ],
)
async def test_light_strip_services(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    service: str,
    service_data: dict,
    mock_method: str,
    expected_args: Any,
    color_modes: set | None,
    color_mode: switchbotColorMode | None,
) -> None:
    """Test all SwitchBot light strip services with proper parameters."""
    inject_bluetooth_service_info(hass, WOSTRIP_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="light_strip")
    entry.add_to_hass(hass)
    entity_id = "light.test_name"

    with (
        patch("switchbot.SwitchbotLightStrip.color_modes", new=color_modes),
        patch("switchbot.SwitchbotLightStrip.color_mode", new=color_mode),
        patch(
            "switchbot.SwitchbotLightStrip.turn_on",
            new=AsyncMock(return_value=True),
        ) as mock_turn_on,
        patch(
            "switchbot.SwitchbotLightStrip.turn_off",
            new=AsyncMock(return_value=True),
        ) as mock_turn_off,
        patch(
            "switchbot.SwitchbotLightStrip.set_brightness",
            new=AsyncMock(return_value=True),
        ) as mock_set_brightness,
        patch(
            "switchbot.SwitchbotLightStrip.set_rgb",
            new=AsyncMock(return_value=True),
        ) as mock_set_rgb,
        patch(
            "switchbot.SwitchbotLightStrip.set_color_temp",
            new=AsyncMock(return_value=True),
        ) as mock_set_color_temp,
        patch("switchbot.SwitchbotLightStrip.update", new=AsyncMock(return_value=None)),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            LIGHT_DOMAIN,
            service,
            {**service_data, ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        mock_map = {
            "turn_off": mock_turn_off,
            "turn_on": mock_turn_on,
            "set_brightness": mock_set_brightness,
            "set_rgb": mock_set_rgb,
            "set_color_temp": mock_set_color_temp,
        }
        mock_instance = mock_map[mock_method]
        mock_instance.assert_awaited_once_with(*expected_args)
