"""Representation of a sirenBinary."""

from typing import Any

from zwave_me_ws import ZWaveMeData

from homeassistant.components.siren import SirenEntity, SirenEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ZWaveMePlatform
from .controller import ZWaveMeConfigEntry, ZWaveMeController
from .entity import ZWaveMeEntity

DEVICE_NAME = ZWaveMePlatform.SIREN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ZWaveMeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the siren platform."""

    @callback
    def add_new_device(new_device):
        async_add_entities([ZWaveMeSiren(config_entry.runtime_data, new_device)])

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"ZWAVE_ME_NEW_{DEVICE_NAME.upper()}", add_new_device
        )
    )


class ZWaveMeSiren(ZWaveMeEntity, SirenEntity):
    """Representation of a ZWaveMe siren."""

    def __init__(self, controller: ZWaveMeController, device: ZWaveMeData) -> None:
        """Initialize the device."""
        super().__init__(controller, device)
        self._attr_supported_features = (
            SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the siren."""
        return self.device.level == "on"

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self.controller.zwave_api.send_command(self.device.id, "on")

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self.controller.zwave_api.send_command(self.device.id, "off")
