"""Support for AVM FRITZ!Box update platform."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import AvmWrapper, FritzBoxBaseEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class FritzUpdateEntityEntityDescription(UpdateEntityDescription):
    """Describes AVM FRITZ!Box update entity."""


ENTITY_DESCRIPTION = UpdateEntityDescription(
    name="Firmware Update",
    key="update",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up AVM FRITZ!Box update entities."""
    _LOGGER.debug("Setting up AVM FRITZ!Box update entities")
    avm_wrapper: AvmWrapper = hass.data[DOMAIN][entry.entry_id]

    entities = [FritzBoxUpdateEntity(avm_wrapper, entry.title)]

    async_add_entities(entities)


class FritzBoxUpdateEntity(FritzBoxBaseEntity, UpdateEntity):
    """Mixin for update entity specific attributes."""

    def __init__(
        self,
        avm_wrapper: AvmWrapper,
        device_friendly_name: str,
    ) -> None:
        """Init FRITZ!Box connectivity class."""
        self.entity_description = ENTITY_DESCRIPTION
        self._attr_title = f"{device_friendly_name}"
        self._attr_name = f"{device_friendly_name} {ENTITY_DESCRIPTION.name}"
        self._attr_unique_id = f"{avm_wrapper.unique_id}-{ENTITY_DESCRIPTION.key}"
        super().__init__(avm_wrapper, device_friendly_name)

    _attr_supported_features = UpdateEntityFeature.INSTALL

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        return self._avm_wrapper.current_firmware

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        if self._avm_wrapper.update_available:
            return self._avm_wrapper.latest_firmware
        return self._avm_wrapper.current_firmware

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        await self._avm_wrapper.async_trigger_firmware_update()
