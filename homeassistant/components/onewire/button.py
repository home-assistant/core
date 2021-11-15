"""Support for 1-Wire buttons."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENTITY_CATEGORY_SYSTEM
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .onewirehub import OneWireHub

_LOGGER = logging.getLogger(__name__)


@dataclass
class OneWireButtonEntityDescription(ButtonEntityDescription):
    """Class describing 1-Wire button entities."""


ENTRY_BUTTON_TYPES = {
    "cleanup_registry": OneWireButtonEntityDescription(
        key="cleanup_registry",
        entity_category=ENTITY_CATEGORY_SYSTEM,
        icon="mdi:broom",
        name="Cleanup 1-Wire devices on {}",
    )
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renault entities from config entry."""
    onewirehub: OneWireHub = hass.data[DOMAIN][config_entry.entry_id]

    async def _cleanup_registry(entity: OneWireConfigEntryButtonEntity) -> None:
        # Get registries
        device_registry = dr.async_get(entity.hass)
        # Generate list of all device entries
        registry_devices = list(
            dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
        )
        # Remove devices that don't belong to any entity
        for device in registry_devices:
            if not onewirehub.has_device_in_cache(device):
                _LOGGER.debug(
                    "Removing device `%s` because it is no longer available",
                    device.id,
                )
                device_registry.async_remove_device(device.id)

    async_add_entities(
        [
            OneWireConfigEntryButtonEntity(
                ENTRY_BUTTON_TYPES["cleanup_registry"],
                config_entry,
                _cleanup_registry,
            ),
        ]
    )


class OneWireConfigEntryButtonEntity(ButtonEntity):
    """Implementation of a 1-Wire binary sensor."""

    def __init__(
        self,
        description: OneWireButtonEntityDescription,
        config_entry: ConfigEntry,
        async_press: Callable[[OneWireConfigEntryButtonEntity], Awaitable],
    ) -> None:
        """Initialize the sensor."""
        if TYPE_CHECKING:
            assert description.name
        self.entity_description = description
        self._attr_name = description.name.format(config_entry.title)
        self._async_press = async_press

    async def async_press(self) -> None:
        """Process the button press."""
        await self._async_press(self)
