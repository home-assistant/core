"""Support for X10 dimmer over Mochad."""
from __future__ import annotations

import logging
from typing import Any

from pymochad import controller, device
from pymochad.exceptions import MochadException
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_ADDRESS, CONF_DEVICES, CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import CONF_COMM_TYPE, DOMAIN, REQ_LOCK, MochadCtrl

_LOGGER = logging.getLogger(__name__)
CONF_BRIGHTNESS_LEVELS = "brightness_levels"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): DOMAIN,
        CONF_DEVICES: [
            {
                vol.Optional(CONF_NAME): cv.string,
                vol.Required(CONF_ADDRESS): cv.x10_address,
                vol.Optional(CONF_COMM_TYPE): cv.string,
                vol.Optional(CONF_BRIGHTNESS_LEVELS, default=32): vol.All(
                    vol.Coerce(int), vol.In([32, 64, 256])
                ),
            }
        ],
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up X10 dimmers over a mochad controller."""
    mochad_controller: MochadCtrl = hass.data[DOMAIN]
    devs: list[dict[str, Any]] = config[CONF_DEVICES]
    add_entities([MochadLight(hass, mochad_controller.ctrl, dev) for dev in devs])


class MochadLight(LightEntity):
    """Representation of a X10 dimmer over Mochad."""

    _attr_assumed_state = True  # X10 devices are normally 1-way
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(
        self, hass: HomeAssistant, ctrl: controller.PyMochad, dev: dict[str, Any]
    ) -> None:
        """Initialize a Mochad Light Device."""

        self._controller = ctrl
        self._address: str = dev[CONF_ADDRESS]
        self._attr_name: str = dev.get(CONF_NAME, f"x10_light_dev_{self._address}")
        self._comm_type: str = dev.get(CONF_COMM_TYPE, "pl")
        self.light = device.Device(ctrl, self._address, comm_type=self._comm_type)
        self._attr_brightness = 0
        self._attr_is_on = self._get_device_status()
        self._brightness_levels: int = dev[CONF_BRIGHTNESS_LEVELS] - 1

    def _get_device_status(self) -> bool:
        """Get the status of the light from mochad."""
        with REQ_LOCK:
            status = self.light.get_status().rstrip()
        return status == "on"

    def _calculate_brightness_value(self, value: int) -> int:
        return int(value * (float(self._brightness_levels) / 255.0))

    def _adjust_brightness(self, brightness: int) -> None:
        assert self.brightness is not None
        if self.brightness > brightness:
            bdelta = self.brightness - brightness
            mochad_brightness = self._calculate_brightness_value(bdelta)
            self.light.send_cmd(f"dim {mochad_brightness}")
            self._controller.read_data()
        elif self.brightness < brightness:
            bdelta = brightness - self.brightness
            mochad_brightness = self._calculate_brightness_value(bdelta)
            self.light.send_cmd(f"bright {mochad_brightness}")
            self._controller.read_data()

    def turn_on(self, **kwargs: Any) -> None:
        """Send the command to turn the light on."""
        _LOGGER.debug("Reconnect %s:%s", self._controller.server, self._controller.port)
        brightness: int = kwargs.get(ATTR_BRIGHTNESS, 255)
        with REQ_LOCK:
            try:
                # Recycle socket on new command to recover mochad connection
                self._controller.reconnect()
                if self._brightness_levels > 32:
                    out_brightness = self._calculate_brightness_value(brightness)
                    self.light.send_cmd(f"xdim {out_brightness}")
                    self._controller.read_data()
                else:
                    self.light.send_cmd("on")
                    self._controller.read_data()
                    # There is no persistence for X10 modules so a fresh on command
                    # will be full brightness
                    if self.brightness == 0:
                        self._attr_brightness = 255
                    self._adjust_brightness(brightness)
                self._attr_brightness = brightness
                self._attr_is_on = True
            except (MochadException, OSError) as exc:
                _LOGGER.error("Error with mochad communication: %s", exc)

    def turn_off(self, **kwargs: Any) -> None:
        """Send the command to turn the light on."""
        _LOGGER.debug("Reconnect %s:%s", self._controller.server, self._controller.port)
        with REQ_LOCK:
            try:
                # Recycle socket on new command to recover mochad connection
                self._controller.reconnect()
                self.light.send_cmd("off")
                self._controller.read_data()
                # There is no persistence for X10 modules so we need to prepare
                # to track a fresh on command will full brightness
                if self._brightness_levels == 31:
                    self._attr_brightness = 0
                self._attr_is_on = False
            except (MochadException, OSError) as exc:
                _LOGGER.error("Error with mochad communication: %s", exc)
