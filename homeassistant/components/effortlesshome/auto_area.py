"""Core area functionality."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.area_registry import (
    AreaEntry,
    async_get as async_get_area_registry,
)
from homeassistant.helpers.device_registry import (
    DeviceInfo,
    async_get as async_get_device_registry,
)
from homeassistant.helpers.entity_registry import (
    RegistryEntry,
    async_get as async_get_entity_registry,
)
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.util import slugify

from .const import (
    DOMAIN,
    ISSUE_TYPE_INVALID_AREA,
    NAME,
    RELEVANT_DOMAINS,
    VERSION,
    DOMAIN,
)
from .ha_helpers import get_all_entities, is_valid_entity

_LOGGER: logging.Logger = logging.getLogger(__package__)


class AutoAreasError(Exception):
    """Exception to indicate a general API error."""


class AutoArea:
    """Class to manage fetching data from the API."""

    # config_entry: ConfigEntry
    area_id = ""

    #    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
    def __init__(self, hass: HomeAssistant, areaid) -> None:
        """Initialize."""
        _LOGGER.info('🤖 Auto Area "%s" ', areaid)
        self.hass = hass
        # self.config_entry = entry

        self.area_registry = async_get_area_registry(self.hass)
        self.device_registry = async_get_device_registry(self.hass)
        self.entity_registry = async_get_entity_registry(self.hass)

        self.area_id = areaid
        self.area: AreaEntry | None = self.area_registry.async_get_area(
            self.area_id or ""
        )

        self.auto_lights = None

    async def async_initialize(self):
        """Subscribe to area changes and reload if necessary."""
        _LOGGER.info("%s: Initializing after HA start", self.area_name)

    def cleanup(self):
        """Deinitialize this area."""
        _LOGGER.debug("%s: Disabling area control", self.area_name)
        if self.auto_lights:
            self.auto_lights.cleanup()

    def get_valid_entities(self) -> list[RegistryEntry]:
        """Return all valid and relevant entities for this area."""
        entities = [
            entity
            for entity in get_all_entities(
                self.entity_registry,
                self.device_registry,
                self.area_id or "",
                RELEVANT_DOMAINS,
            )
            if is_valid_entity(self.hass, entity)
        ]
        return entities

    def get_area_entity_ids(self, device_classes: list[str]) -> list[str]:
        """Return all entity ids in a list of device classes."""
        return [
            entity.entity_id
            for entity in self.get_valid_entities()
            if entity.device_class in device_classes
            or entity.original_device_class in device_classes
        ]

    @property
    def device_info(self) -> DeviceInfo:
        """Information about this device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "model": NAME,
            "manufacturer": NAME,
            "suggested_area": self.area_name,
        }

    @property
    def area_name(self) -> str:
        """Return area name or fallback."""
        return self.area.name if self.area is not None else "unknown"

    @property
    def slugified_area_name(self) -> str:
        """Return slugified area name or fallback."""
        return slugify(self.area.name) if self.area is not None else "unknown"
