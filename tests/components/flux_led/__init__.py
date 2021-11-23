"""Tests for the flux_led integration."""
from __future__ import annotations

import asyncio
from typing import Callable
from unittest.mock import AsyncMock, MagicMock, patch

from flux_led import DeviceType
from flux_led.aio import AIOWifiLedBulb
from flux_led.const import (
    ATTR_ID,
    ATTR_IPADDR,
    ATTR_MODEL,
    ATTR_MODEL_DESCRIPTION,
    COLOR_MODE_CCT as FLUX_COLOR_MODE_CCT,
    COLOR_MODE_RGB as FLUX_COLOR_MODE_RGB,
)
from flux_led.protocol import LEDENETRawState

from homeassistant.components import dhcp
from homeassistant.core import HomeAssistant

MODULE = "homeassistant.components.flux_led"
MODULE_CONFIG_FLOW = "homeassistant.components.flux_led.config_flow"
IP_ADDRESS = "127.0.0.1"
MODEL = "AZ120444"
MODEL_DESCRIPTION = "RGBW Controller"
MAC_ADDRESS = "aa:bb:cc:dd:ee:ff"
FLUX_MAC_ADDRESS = "aabbccddeeff"
SHORT_MAC_ADDRESS = "ddeeff"

DEFAULT_ENTRY_TITLE = f"{MODEL_DESCRIPTION} {SHORT_MAC_ADDRESS}"
DEFAULT_ENTRY_TITLE_PARTIAL = f"{MODEL} {SHORT_MAC_ADDRESS}"


DHCP_DISCOVERY = dhcp.DhcpServiceInfo(
    hostname=MODEL,
    ip=IP_ADDRESS,
    macaddress=MAC_ADDRESS,
)
FLUX_DISCOVERY_PARTIAL = {
    ATTR_IPADDR: IP_ADDRESS,
    ATTR_MODEL: MODEL,
    ATTR_ID: FLUX_MAC_ADDRESS,
}
FLUX_DISCOVERY = {
    ATTR_IPADDR: IP_ADDRESS,
    ATTR_MODEL: MODEL,
    ATTR_ID: FLUX_MAC_ADDRESS,
    ATTR_MODEL_DESCRIPTION: MODEL_DESCRIPTION,
}


def _mocked_bulb() -> AIOWifiLedBulb:
    bulb = MagicMock(auto_spec=AIOWifiLedBulb)

    async def _save_setup_callback(callback: Callable) -> None:
        bulb.data_receive_callback = callback

    bulb.device_type = DeviceType.Bulb
    bulb.async_setup = AsyncMock(side_effect=_save_setup_callback)
    bulb.effect_list = ["some_effect"]
    bulb.async_set_custom_pattern = AsyncMock()
    bulb.async_set_preset_pattern = AsyncMock()
    bulb.async_set_effect = AsyncMock()
    bulb.async_set_white_temp = AsyncMock()
    bulb.async_stop = AsyncMock()
    bulb.async_update = AsyncMock()
    bulb.async_turn_off = AsyncMock()
    bulb.async_turn_on = AsyncMock()
    bulb.async_set_levels = AsyncMock()
    bulb.min_temp = 2700
    bulb.max_temp = 6500
    bulb.getRgb = MagicMock(return_value=[255, 0, 0])
    bulb.getRgbw = MagicMock(return_value=[255, 0, 0, 50])
    bulb.getRgbww = MagicMock(return_value=[255, 0, 0, 50, 0])
    bulb.getRgbcw = MagicMock(return_value=[255, 0, 0, 0, 50])
    bulb.rgb = (255, 0, 0)
    bulb.rgbw = (255, 0, 0, 50)
    bulb.rgbww = (255, 0, 0, 50, 0)
    bulb.rgbcw = (255, 0, 0, 0, 50)
    bulb.color_temp = 2700
    bulb.getWhiteTemperature = MagicMock(return_value=(2700, 128))
    bulb.brightness = 128
    bulb.model_num = 0x35
    bulb.effect = None
    bulb.speed = 50
    bulb.model = "Smart Bulb (0x35)"
    bulb.version_num = 8
    bulb.original_addressable = False
    bulb.addressable = False
    bulb.rgbwcapable = True
    bulb.color_modes = {FLUX_COLOR_MODE_RGB, FLUX_COLOR_MODE_CCT}
    bulb.color_mode = FLUX_COLOR_MODE_RGB
    bulb.raw_state = LEDENETRawState(
        0, 0x35, 0, 0x61, 0x5, 50, 255, 0, 0, 50, 8, 0, 0, 0
    )
    return bulb


def _mocked_switch() -> AIOWifiLedBulb:
    switch = MagicMock(auto_spec=AIOWifiLedBulb)

    async def _save_setup_callback(callback: Callable) -> None:
        switch.data_receive_callback = callback

    switch.device_type = DeviceType.Switch
    switch.async_setup = AsyncMock(side_effect=_save_setup_callback)
    switch.async_stop = AsyncMock()
    switch.async_update = AsyncMock()
    switch.async_turn_off = AsyncMock()
    switch.async_turn_on = AsyncMock()
    switch.model_num = 0x97
    switch.model = "Smart Switch (0x97)"
    switch.version_num = 0x97
    switch.raw_state = LEDENETRawState(
        0, 0x97, 0, 0x61, 0x97, 50, 255, 0, 0, 50, 8, 0, 0, 0
    )
    return switch


async def async_mock_device_turn_off(hass: HomeAssistant, bulb: AIOWifiLedBulb) -> None:
    """Mock the device being off."""
    bulb.is_on = False
    bulb.raw_state._replace(power_state=0x24)
    bulb.data_receive_callback()
    await hass.async_block_till_done()


async def async_mock_device_turn_on(hass: HomeAssistant, bulb: AIOWifiLedBulb) -> None:
    """Mock the device being on."""
    bulb.is_on = True
    bulb.raw_state._replace(power_state=0x23)
    bulb.data_receive_callback()
    await hass.async_block_till_done()


async def async_mock_effect_speed(
    hass: HomeAssistant, bulb: AIOWifiLedBulb, effect: str, speed: int
) -> None:
    """Mock the device being on with an effect."""
    bulb.speed = speed
    bulb.effect = effect
    bulb.data_receive_callback()
    await hass.async_block_till_done()


def _patch_discovery(device=None, no_device=False):
    async def _discovery(*args, **kwargs):
        if no_device:
            raise OSError
        return [FLUX_DISCOVERY]

    return patch(
        "homeassistant.components.flux_led.AIOBulbScanner.async_scan", new=_discovery
    )


def _patch_wifibulb(device=None, no_device=False):
    def _wifi_led_bulb(*args, **kwargs):
        bulb = _mocked_bulb()
        if no_device:
            bulb.async_setup = AsyncMock(side_effect=asyncio.TimeoutError)
            return bulb
        return device if device else _mocked_bulb()

    return patch("homeassistant.components.flux_led.AIOWifiLedBulb", new=_wifi_led_bulb)
