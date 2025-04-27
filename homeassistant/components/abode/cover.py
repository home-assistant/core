"""Support for Abode Security System covers."""

from typing import Any

from jaraco.abode.devices.cover import Cover

from homeassistant.components.cover import CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AbodeSystem
from .const import DOMAIN
from .entity import AbodeDevice


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Abode cover devices."""
    data: AbodeSystem = hass.data[DOMAIN]

    async_add_entities(
        AbodeCover(data, device)
        for device in data.abode.get_devices(generic_type="cover")
    )


class AbodeCover(AbodeDevice, CoverEntity):
    """Representation of an Abode cover."""

    _device: Cover
    _attr_name = None

    @property
    def is_closed(self) -> bool:
        """Return true if cover is closed, else False."""
        return not self._device.is_open

    def close_cover(self, **kwargs: Any) -> None:
        """Issue close command to cover."""
        self._device.close_cover()

    def open_cover(self, **kwargs: Any) -> None:
        """Issue open command to cover."""
        self._device.open_cover()
