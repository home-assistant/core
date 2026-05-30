"""Representation of a switchBinary."""

import logging
from typing import Any

from zwave_me_ws import ZWaveMeData

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ZWaveMePlatform
from .controller import ZWaveMeConfigEntry, ZWaveMeController
from .entity import ZWaveMeEntity

_LOGGER = logging.getLogger(__name__)
DEVICE_NAME = ZWaveMePlatform.SWITCH

SWITCH_MAP: dict[str, SwitchEntityDescription] = {
    "generic": SwitchEntityDescription(
        key="generic",
        device_class=SwitchDeviceClass.SWITCH,
    )
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ZWaveMeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch platform."""

    @callback
    def add_new_device(new_device):
        async_add_entities(
            [
                ZWaveMeSwitch(
                    config_entry.runtime_data, new_device, SWITCH_MAP["generic"]
                )
            ]
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"ZWAVE_ME_NEW_{DEVICE_NAME.upper()}", add_new_device
        )
    )


class ZWaveMeSwitch(ZWaveMeEntity, SwitchEntity):
    """Representation of a ZWaveMe binary switch."""

    def __init__(
        self,
        controller: ZWaveMeController,
        device: ZWaveMeData,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the device."""
        super().__init__(controller, device)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self.device.level == "on"

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self.controller.zwave_api.send_command(self.device.id, "on")

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self.controller.zwave_api.send_command(self.device.id, "off")
