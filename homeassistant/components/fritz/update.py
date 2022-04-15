"""Support for AVM FRITZ!Box update platform."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Final

from homeassistant.components.update import UpdateEntity, UpdateEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import AvmWrapper, FritzBoxBaseEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class FritzUpdateEntityEntityDescription(UpdateEntityDescription):
    """Describes AVM FRITZ!Box update entity."""


UPDATE_ENTITIES: Final = [
    FritzUpdateEntityEntityDescription(
        key="update",
        name="Firmware Update",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up AVM FRITZ!Box update entities."""
    _LOGGER.debug("Setting up AVM FRITZ!Box update entities")
    avm_wrapper: AvmWrapper = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        FritzBoxUpdateEntity(avm_wrapper, entry.title, description)
        for description in UPDATE_ENTITIES
    )


class FritzBoxUpdateEntity(FritzBoxBaseEntity, UpdateEntity):
    """Mixin for update entity specific attributes."""

    def __init__(
        self,
        avm_wrapper: AvmWrapper,
        device_friendly_name: str,
        description: FritzUpdateEntityEntityDescription,
    ) -> None:
        """Init FRITZ!Box connectivity class."""
        self.entity_description = description
        self._attr_name = f"{device_friendly_name} {description.name}"
        self._attr_unique_id = f"{avm_wrapper.unique_id}-{description.key}"
        super().__init__(avm_wrapper, device_friendly_name)

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        return self._avm_wrapper.current_firmware.partition(".")[2]

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        if self._avm_wrapper.update_available:
            return (
                self._avm_wrapper.latest_firmware.partition(".")[2]
                if self._avm_wrapper.latest_firmware
                else None
            )
        return (
            self._avm_wrapper.current_firmware.partition(".")[2]
            if self._avm_wrapper.current_firmware
            else None
        )
