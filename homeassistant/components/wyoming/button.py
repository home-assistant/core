"""Wyoming button entities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import WyomingSatelliteEntity

if TYPE_CHECKING:
    from .models import DomainDataItem


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities."""
    item: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]

    # Setup is only forwarded for satellites
    assert item.satellite is not None

    async_add_entities([WyomingSatelliteForceActivate(item.satellite.device)])


class WyomingSatelliteForceActivate(WyomingSatelliteEntity, ButtonEntity):
    """Manually activate the satellite instead of using a wake word."""

    entity_description = ButtonEntityDescription(
        key="activate",
        translation_key="activat",
    )

    async def async_press(self, **kwargs: Any) -> None:
        """Turn on."""
        self._device.force_activate()
