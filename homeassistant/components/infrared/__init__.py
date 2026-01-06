"""Support for infrared transmitter entities."""

from __future__ import annotations

from abc import abstractmethod
from datetime import timedelta
import logging
from typing import Any

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, InfraredEntityFeature
from .protocols import (
    PULSE_WIDTH_COMPAT_PROTOCOLS,
    InfraredCommand,
    InfraredProtocol,
    InfraredProtocolType,
    IRTiming,
    NECInfraredCommand,
    NECInfraredProtocol,
    PulseWidthInfraredCommand,
    PulseWidthIRProtocol,
    SamsungInfraredCommand,
    SamsungInfraredProtocol,
)

__all__ = [
    "DOMAIN",
    "PULSE_WIDTH_COMPAT_PROTOCOLS",
    "IRTiming",
    "InfraredCommand",
    "InfraredEntity",
    "InfraredEntityDescription",
    "InfraredEntityFeature",
    "InfraredProtocol",
    "InfraredProtocolType",
    "NECInfraredCommand",
    "NECInfraredProtocol",
    "PulseWidthIRProtocol",
    "PulseWidthInfraredCommand",
    "SamsungInfraredCommand",
    "SamsungInfraredProtocol",
    "async_get_entities",
    "async_send_command",
]

_LOGGER = logging.getLogger(__name__)

DATA_COMPONENT: HassKey[EntityComponent[InfraredEntity]] = HassKey(DOMAIN)
ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the infrared domain."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[InfraredEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


@callback
def async_get_entities(
    hass: HomeAssistant, protocols: set[str] | None = None
) -> list[InfraredEntity]:
    """Get all infrared entities, optionally filtered by protocol support."""
    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        return []

    entities = list(component.entities)
    if protocols is not None:
        protocol_set = set(protocols)
        entities = [e for e in entities if e.supported_protocols & protocol_set]
    return entities


async def async_send_command(
    hass: HomeAssistant, entity_id: str, command: InfraredCommand
) -> None:
    """Send an IR command to the specified infrared entity.

    Raises:
        HomeAssistantError: If the infrared entity is not found.
    """
    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        raise HomeAssistantError("Infrared component not loaded.")

    entity = component.get_entity(entity_id)
    if entity is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="entity_not_found",
            translation_placeholders={"entity_id": entity_id},
        )

    await entity.async_send_command(command)


class InfraredEntityDescription(EntityDescription, frozen_or_thawed=True):
    """Describes infrared entities."""


CACHED_PROPERTIES_WITH_ATTR_ = {
    "supported_features",
    "supported_protocols",
}


ATTR_SUPPORTED_PROTOCOLS = "supported_protocols"


class InfraredEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Base class for infrared transmitter entities."""

    entity_description: InfraredEntityDescription
    _attr_supported_features: InfraredEntityFeature = InfraredEntityFeature(0)
    _attr_supported_protocols: set[str] = set()

    @cached_property
    def supported_features(self) -> InfraredEntityFeature:
        """Flag supported features."""
        return self._attr_supported_features

    @cached_property
    def supported_protocols(self) -> set[str]:
        """Return set of supported IR protocol types."""
        return self._attr_supported_protocols

    @property
    def capability_attributes(self) -> dict[str, Any] | None:
        """Return capability attributes."""
        return {ATTR_SUPPORTED_PROTOCOLS: sorted(self.supported_protocols)}

    @abstractmethod
    async def async_send_command(self, command: InfraredCommand) -> None:
        """Send an IR command.

        Args:
            command: The IR command to send.

        Raises:
            HomeAssistantError: If transmission fails.
        """
