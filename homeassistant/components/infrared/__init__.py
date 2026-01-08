"""Support for infrared transmitter entities."""

from __future__ import annotations

from abc import abstractmethod
from datetime import datetime, timedelta
import logging
from typing import final

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, InfraredEntityFeature
from .protocols import InfraredCommand, InfraredProtocol, NECInfraredCommand, Timing

__all__ = [
    "DOMAIN",
    "InfraredCommand",
    "InfraredEntity",
    "InfraredEntityDescription",
    "InfraredEntityFeature",
    "InfraredProtocol",
    "NECInfraredCommand",
    "Timing",
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
    hass: HomeAssistant, supported_features: InfraredEntityFeature
) -> list[InfraredEntity]:
    """Get all infrared entities that support the given features."""
    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        return []

    return [
        entity
        for entity in component.entities
        if entity.supported_features & supported_features
    ]


async def async_send_command(
    hass: HomeAssistant,
    entity_id: str,
    command: InfraredCommand,
    context: Context | None = None,
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

    if context is not None:
        entity.async_set_context(context)

    await entity.async_send_command_internal(command)


class InfraredEntityDescription(EntityDescription, frozen_or_thawed=True):
    """Describes infrared entities."""


CACHED_PROPERTIES_WITH_ATTR_ = {"supported_features"}


class InfraredEntity(RestoreEntity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Base class for infrared transmitter entities."""

    entity_description: InfraredEntityDescription
    _attr_supported_features: InfraredEntityFeature = InfraredEntityFeature(0)
    _attr_should_poll = False
    _attr_state: None

    __last_command_sent: datetime | None = None

    @cached_property
    def supported_features(self) -> InfraredEntityFeature:
        """Flag supported features."""
        return self._attr_supported_features

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        if (last_command := self.__last_command_sent) is None:
            return None
        return last_command.isoformat(timespec="milliseconds")

    @final
    async def async_send_command_internal(self, command: InfraredCommand) -> None:
        """Send an IR command and update state.

        Should not be overridden, handles setting last sent timestamp.
        """
        self.__last_command_sent = dt_util.utcnow()
        self.async_write_ha_state()
        await self.async_send_command(command)

    @final
    async def async_internal_added_to_hass(self) -> None:
        """Call when the infrared entity is added to hass."""
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state is not None:
            self.__last_command_sent = dt_util.parse_datetime(state.state)

    @abstractmethod
    async def async_send_command(self, command: InfraredCommand) -> None:
        """Send an IR command.

        Args:
            command: The IR command to send.

        Raises:
            HomeAssistantError: If transmission fails.
        """
