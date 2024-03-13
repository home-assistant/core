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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import AvmWrapper, FritzBoxBaseCoordinatorEntity, FritzEntityDescription
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class FritzUpdateEntityDescription(UpdateEntityDescription, FritzEntityDescription):
    """Describes Fritz update entity."""


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up AVM FRITZ!Box update entities."""
    _LOGGER.debug("Setting up AVM FRITZ!Box update entities")
    avm_wrapper: AvmWrapper = hass.data[DOMAIN][entry.entry_id]

    entities = [FritzBoxUpdateEntity(avm_wrapper, entry.title)]

    async_add_entities(entities)


class FritzBoxUpdateEntity(FritzBoxBaseCoordinatorEntity, UpdateEntity):
    """Mixin for update entity specific attributes."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_supported_features = UpdateEntityFeature.INSTALL
    _attr_title = "FRITZ!OS"
    entity_description: FritzUpdateEntityDescription

    def __init__(
        self,
        avm_wrapper: AvmWrapper,
        device_friendly_name: str,
    ) -> None:
        """Init FRITZ!Box connectivity class."""
        description = FritzUpdateEntityDescription(
            key="update", name="FRITZ!OS", value_fn=None
        )
        super().__init__(avm_wrapper, device_friendly_name, description)

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        return self.coordinator.current_firmware

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        if self.coordinator.update_available:
            return self.coordinator.latest_firmware
        return self.coordinator.current_firmware

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        return self.coordinator.release_url

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        await self.coordinator.async_trigger_firmware_update()
