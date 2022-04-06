"""Tests for the flux_led integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import contextmanager
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from flux_led import DeviceType
from flux_led.aio import AIOWifiLedBulb
from flux_led.const import (
    COLOR_MODE_CCT as FLUX_COLOR_MODE_CCT,
    COLOR_MODE_RGB as FLUX_COLOR_MODE_RGB,
    WhiteChannelType,
)
from flux_led.models_db import MODEL_MAP
from flux_led.protocol import (
    LEDENETRawState,
    PowerRestoreState,
    PowerRestoreStates,
    RemoteConfig,
)
from flux_led.scanner import FluxLEDDiscovery

from homeassistant.components import dhcp
from homeassistant.components.flux_led.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MODULE = "homeassistant.components.flux_led"
MODULE_CONFIG_FLOW = "homeassistant.components.flux_led.config_flow"
IP_ADDRESS = "127.0.0.1"
MODEL_NUM_HEX = "0x35"
MODEL_NUM = 0x35
MODEL = "AK001-ZJ2149"
MODEL_DESCRIPTION = "Bulb RGBCW"
MAC_ADDRESS = "aa:bb:cc:dd:ee:ff"
MAC_ADDRESS_ONE_OFF = "aa:bb:cc:dd:ee:fe"

FLUX_MAC_ADDRESS = "AABBCCDDEEFF"
SHORT_MAC_ADDRESS = "DDEEFF"

DEFAULT_ENTRY_TITLE = f"{MODEL_DESCRIPTION} {SHORT_MAC_ADDRESS}"


DHCP_DISCOVERY = dhcp.DhcpServiceInfo(
    hostname=MODEL,
    ip=IP_ADDRESS,
    macaddress=MAC_ADDRESS,
)
FLUX_DISCOVERY_PARTIAL = FluxLEDDiscovery(
    ipaddr=IP_ADDRESS,
    model=MODEL,
    id=FLUX_MAC_ADDRESS,
    model_num=None,
    version_num=None,
    firmware_date=None,
    model_info=None,
    model_description=None,
)
FLUX_DISCOVERY = FluxLEDDiscovery(
    ipaddr=IP_ADDRESS,
    model=MODEL,
    id=FLUX_MAC_ADDRESS,
    model_num=MODEL_NUM,
    version_num=0x04,
    firmware_date=datetime.date(2021, 5, 5),
    model_info=MODEL,
    model_description=MODEL_DESCRIPTION,
    remote_access_enabled=True,
    remote_access_host="the.cloud",
    remote_access_port=8816,
)


def _mock_config_entry_for_bulb(hass: HomeAssistant) -> ConfigEntry:
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    return config_entry


def _mocked_bulb() -> AIOWifiLedBulb:
    bulb = MagicMock(auto_spec=AIOWifiLedBulb)

    async def _save_setup_callback(callback: Callable) -> None:
        bulb.data_receive_callback = callback

    bulb.device_type = DeviceType.Bulb
    bulb.requires_turn_on = True
    bulb.async_setup = AsyncMock(side_effect=_save_setup_callback)
    bulb.effect_list = ["some_effect"]
    bulb.remote_config = RemoteConfig.OPEN
    bulb.async_unpair_remotes = AsyncMock()
    bulb.async_set_time = AsyncMock()
    bulb.async_set_music_mode = AsyncMock()
    bulb.async_set_custom_pattern = AsyncMock()
    bulb.async_set_preset_pattern = AsyncMock()
    bulb.async_set_effect = AsyncMock()
    bulb.async_set_white_temp = AsyncMock()
    bulb.async_set_brightness = AsyncMock()
    bulb.async_set_device_config = AsyncMock()
    bulb.async_config_remotes = AsyncMock()
    bulb.white_channel_channel_type = WhiteChannelType.WARM
    bulb.paired_remotes = 2
    bulb.pixels_per_segment = 300
    bulb.segments = 2
    bulb.diagnostics = {"mock_diag": "mock_diag"}
    bulb.music_pixels_per_segment = 150
    bulb.music_segments = 4
    bulb.operating_mode = "RGB&W"
    bulb.operating_modes = ["RGB&W", "RGB/W"]
    bulb.wirings = ["RGBW", "GRBW", "BGRW"]
    bulb.wiring = "BGRW"
    bulb.ic_types = ["WS2812B", "UCS1618"]
    bulb.ic_type = "WS2812B"
    bulb.async_stop = AsyncMock()
    bulb.async_update = AsyncMock()
    bulb.async_turn_off = AsyncMock()
    bulb.async_turn_on = AsyncMock()
    bulb.async_set_levels = AsyncMock()
    bulb.async_set_zones = AsyncMock()
    bulb.async_disable_remote_access = AsyncMock()
    bulb.async_enable_remote_access = AsyncMock()
    bulb.min_temp = 2700
    bulb.max_temp = 6500
    bulb.getRgb = MagicMock(return_value=[255, 0, 0])
    bulb.getRgbw = MagicMock(return_value=[255, 0, 0, 50])
    bulb.getRgbww = MagicMock(return_value=[255, 0, 0, 50, 0])
    bulb.getRgbcw = MagicMock(return_value=[255, 0, 0, 0, 50])
    bulb.rgb = (255, 0, 0)
    bulb.rgb_unscaled = (255, 0, 0)
    bulb.rgbw = (255, 0, 0, 50)
    bulb.rgbww = (255, 0, 0, 50, 0)
    bulb.rgbcw = (255, 0, 0, 0, 50)
    bulb.color_temp = 2700
    bulb.getWhiteTemperature = MagicMock(return_value=(2700, 128))
    bulb.brightness = 128
    bulb.model_num = MODEL_NUM
    bulb.model_data = MODEL_MAP[MODEL_NUM]
    bulb.effect = None
    bulb.speed = 50
    bulb.model = "Bulb RGBCW (0x35)"
    bulb.version_num = 8
    bulb.speed_adjust_off = True
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
    switch.power_restore_states = PowerRestoreStates(
        channel1=PowerRestoreState.LAST_STATE,
        channel2=PowerRestoreState.LAST_STATE,
        channel3=PowerRestoreState.LAST_STATE,
        channel4=PowerRestoreState.LAST_STATE,
    )
    switch.pixels_per_segment = None
    switch.segments = None
    switch.music_pixels_per_segment = None
    switch.music_segments = None
    switch.operating_mode = None
    switch.operating_modes = None
    switch.wirings = None
    switch.wiring = None
    switch.ic_types = None
    switch.ic_type = None
    switch.requires_turn_on = True
    switch.async_set_time = AsyncMock()
    switch.async_reboot = AsyncMock()
    switch.async_setup = AsyncMock(side_effect=_save_setup_callback)
    switch.async_set_power_restore = AsyncMock()
    switch.async_stop = AsyncMock()
    switch.async_update = AsyncMock()
    switch.async_turn_off = AsyncMock()
    switch.async_turn_on = AsyncMock()
    switch.model_num = 0x97
    switch.model_data = MODEL_MAP[0x97]
    switch.model = "Switch (0x97)"
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
        return [] if no_device else [device or FLUX_DISCOVERY]

    @contextmanager
    def _patcher():
        with patch(
            "homeassistant.components.flux_led.discovery.AIOBulbScanner.async_scan",
            new=_discovery,
        ), patch(
            "homeassistant.components.flux_led.discovery.AIOBulbScanner.getBulbInfo",
            return_value=[] if no_device else [device or FLUX_DISCOVERY],
        ):
            yield

    return _patcher()


def _patch_wifibulb(device=None, no_device=False):
    def _wifi_led_bulb(*args, **kwargs):
        bulb = _mocked_bulb()
        if no_device:
            bulb.async_setup = AsyncMock(side_effect=asyncio.TimeoutError)
            return bulb
        return device if device else _mocked_bulb()

    return patch("homeassistant.components.flux_led.AIOWifiLedBulb", new=_wifi_led_bulb)
