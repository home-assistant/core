"""Support for X10 switch over Mochad."""
from __future__ import annotations

import logging
from typing import Any

from pymochad import controller, device
from pymochad.exceptions import MochadException
import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_ADDRESS, CONF_DEVICES, CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import CONF_COMM_TYPE, DOMAIN, REQ_LOCK, MochadCtrl

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): DOMAIN,
        CONF_DEVICES: [
            {
                vol.Optional(CONF_NAME): cv.string,
                vol.Required(CONF_ADDRESS): cv.x10_address,
                vol.Optional(CONF_COMM_TYPE): cv.string,
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
    """Set up X10 switches over a mochad controller."""
    mochad_controller: MochadCtrl = hass.data[DOMAIN]
    devs: list[dict[str, str]] = config[CONF_DEVICES]
    add_entities([MochadSwitch(hass, mochad_controller.ctrl, dev) for dev in devs])


class MochadSwitch(SwitchEntity):
    """Representation of a X10 switch over Mochad."""

    def __init__(
        self, hass: HomeAssistant, ctrl: controller.PyMochad, dev: dict[str, str]
    ) -> None:
        """Initialize a Mochad Switch Device."""

        self._controller = ctrl
        self._address: str = dev[CONF_ADDRESS]
        self._attr_name: str = dev.get(CONF_NAME, f"x10_switch_dev_{self._address}")
        self._comm_type: str = dev.get(CONF_COMM_TYPE, "pl")
        self.switch = device.Device(ctrl, self._address, comm_type=self._comm_type)
        # Init with false to avoid locking HA for long on CM19A (goes from rf
        # to pl via TM751, but not other way around)
        if self._comm_type == "pl":
            self._attr_is_on = self._get_device_status()
        else:
            self._attr_is_on = False

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""

        _LOGGER.debug("Reconnect %s:%s", self._controller.server, self._controller.port)
        with REQ_LOCK:
            try:
                # Recycle socket on new command to recover mochad connection
                self._controller.reconnect()
                self.switch.send_cmd("on")
                # No read data on CM19A which is rf only
                if self._comm_type == "pl":
                    self._controller.read_data()
                self._attr_is_on = True
            except (MochadException, OSError) as exc:
                _LOGGER.error("Error with mochad communication: %s", exc)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""

        _LOGGER.debug("Reconnect %s:%s", self._controller.server, self._controller.port)
        with REQ_LOCK:
            try:
                # Recycle socket on new command to recover mochad connection
                self._controller.reconnect()
                self.switch.send_cmd("off")
                # No read data on CM19A which is rf only
                if self._comm_type == "pl":
                    self._controller.read_data()
                self._attr_is_on = False
            except (MochadException, OSError) as exc:
                _LOGGER.error("Error with mochad communication: %s", exc)

    def _get_device_status(self) -> bool:
        """Get the status of the switch from mochad."""
        with REQ_LOCK:
            status = self.switch.get_status().rstrip()
        return status == "on"
