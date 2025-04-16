"""Test the switchbot lights."""

from collections.abc import Callable
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
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import HomeAssistant

from . import WOSTRIP_SERVICE_INFO

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
            SERVICE_TURN_OFF,
            {},
            "turn_off",
        ),
        (
            SERVICE_TURN_ON,
            {},
            "turn_on",
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_BRIGHTNESS: 128},
            "set_brightness",
        ),
        (
            SERVICE_TURN_ON,
            {ATTR_RGB_COLOR: (255, 0, 0)},
            "set_rgb",
        ),
    ],
)
async def test_light_strip_controlling(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    service: str,
    service_data: dict,
    mock_method: str,
) -> None:
    """Test controlling the light strip with parametrized services."""
    inject_bluetooth_service_info(hass, WOSTRIP_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="light_strip")
    entry.add_to_hass(hass)

    entity_id = "light.test_name"

    with (
        patch("switchbot.SwitchbotLightStrip.update", AsyncMock(return_value=None)),
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
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        initial_state = hass.states.get(entity_id)
        assert initial_state is not None
        assert initial_state.state == STATE_ON

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
        }
        mock_instance = mock_map[mock_method]
        mock_instance.assert_awaited_once()


async def test_light_strip_kelvin_temp(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test setting color temperature when the device supports it."""
    inject_bluetooth_service_info(hass, WOSTRIP_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="light_strip")
    entry.add_to_hass(hass)

    entity_id = "light.test_name"

    with (
        patch("switchbot.SwitchbotLightStrip.update", new=AsyncMock(return_value=True)),
        patch(
            "switchbot.SwitchbotLightStrip.turn_on", new=AsyncMock(return_value=True)
        ),
        patch(
            "switchbot.SwitchbotLightStrip.set_color_temp",
            new=AsyncMock(return_value=True),
        ) as mock_set_color_temp,
        patch(
            "switchbot.SwitchbotLightStrip.color_modes",
            new_callable=lambda: {switchbotColorMode.COLOR_TEMP},
        ),
        patch(
            "switchbot.SwitchbotLightStrip.color_mode",
            new_callable=lambda: switchbotColorMode.COLOR_TEMP,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 4000},
            blocking=True,
        )
        mock_set_color_temp.assert_awaited_once()
