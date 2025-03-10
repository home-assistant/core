"""Test the switchbot lights."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from switchbot import ColorMode as switchbotColorMode

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    ColorMode,
)
from homeassistant.components.switchbot.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ADDRESS,
    CONF_NAME,
    CONF_SENSOR_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import WOSTRIP_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_light_strip_controlling(hass: HomeAssistant) -> None:
    """Test setting up and controlling the light strip."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOSTRIP_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "light_strip",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    entity_id = "light.test_name"

    with (
        patch("switchbot.SwitchbotLightStrip.update", new=Mock(return_value=True)),
        patch(
            "switchbot.SwitchbotLightStrip.turn_on", new=AsyncMock(return_value=True)
        ) as mock_turn_on,
        patch(
            "switchbot.SwitchbotLightStrip.turn_off", new=AsyncMock(return_value=True)
        ) as mock_turn_off,
        patch(
            "switchbot.SwitchbotLightStrip.set_brightness",
            new=AsyncMock(return_value=True),
        ) as mock_set_brightness,
        patch(
            "switchbot.SwitchbotLightStrip.set_rgb", new=AsyncMock(return_value=True)
        ) as mock_set_rgb,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "on"

        # Test turn off
        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_turn_off.assert_awaited_once()
        state = hass.states.get(entity_id)
        assert state.state == "off"

        # Test turn on
        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_turn_on.assert_awaited_once()
        state = hass.states.get(entity_id)
        assert state.state == "on"

        # Test set brightness
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128},
            blocking=True,
        )
        mock_set_brightness.assert_awaited_once_with(50)
        state = hass.states.get(entity_id)
        assert state.attributes[ATTR_BRIGHTNESS] == 50

        # Test set RGB
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id, ATTR_RGB_COLOR: (255, 0, 0)},
            blocking=True,
        )
        mock_set_rgb.assert_awaited_once_with(20, 255, 0, 0)
        state = hass.states.get(entity_id)
        assert state.attributes[ATTR_RGB_COLOR] == (255, 0, 0)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_light_strip_kelvin_supported(hass: HomeAssistant) -> None:
    """Test setting color temperature when the device supports it."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOSTRIP_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "light_strip",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    entity_id = "light.test_name"
    with (
        patch("switchbot.SwitchbotLightStrip.update", new=Mock(return_value=True)),
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

        state = hass.states.get(entity_id)
        assert state.attributes["color_mode"] == ColorMode.COLOR_TEMP
        assert state.attributes["color_temp_kelvin"] == 4000
