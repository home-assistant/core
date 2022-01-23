"""Representation of a switchBinary."""
import logging

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import ZWaveMeEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
DEVICE_NAME = "switchBinary"

SWITCH_MAP: dict[str, SwitchEntityDescription] = {
    "generic": SwitchEntityDescription(
        key="generic",
        device_class=SwitchDeviceClass.SWITCH,
    )
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the switch platform."""

    @callback
    def add_new_device(new_device):
        controller = hass.data[DOMAIN][config_entry.entry_id]
        switch = ZWaveMeSwitch(controller, new_device, SWITCH_MAP["generic"])

        async_add_entities(
            [
                switch,
            ]
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"ZWAVE_ME_NEW_{DEVICE_NAME.upper()}", add_new_device
        )
    )


class ZWaveMeSwitch(ZWaveMeEntity, SwitchEntity):
    """Representation of a ZWaveMe binary switch."""

    def __init__(self, controller, device, description):
        """Initialize the device."""
        ZWaveMeEntity.__init__(self, controller, device)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self.device.level == "on"

    def turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        self.controller.zwave_api.send_command(self.device.id, "on")

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        self.controller.zwave_api.send_command(self.device.id, "off")

    @property
    def device_class(self) -> str:
        """Return the device class."""
        return self.entity_description.device_class
