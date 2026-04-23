"""Provides functionality to interact with radio frequency devices."""

from __future__ import annotations

from abc import abstractmethod
from datetime import timedelta
import logging
from typing import final

from rf_protocols import ModulationType, RadioFrequencyCommand

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

__all__ = [
    "DOMAIN",
    "ModulationType",
    "RadioFrequencyTransmitterEntity",
    "RadioFrequencyTransmitterEntityDescription",
    "async_get_transmitters",
    "async_send_command",
]

_LOGGER = logging.getLogger(__name__)

DATA_COMPONENT: HassKey[EntityComponent[RadioFrequencyTransmitterEntity]] = HassKey(
    DOMAIN
)
ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the radio_frequency domain."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[
        RadioFrequencyTransmitterEntity
    ](_LOGGER, DOMAIN, hass, SCAN_INTERVAL)
    await component.async_setup(config)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


@callback
def async_get_transmitters(
    hass: HomeAssistant,
    frequency: int,
    modulation: ModulationType,
) -> list[str]:
    """Get entity IDs of all RF transmitters supporting the given frequency.

    Transmitters are filtered by both their supported frequency ranges and
    their supported modulation types. An empty list means no compatible
    transmitters.

    Raises:
        HomeAssistantError: If the component is not loaded or if no
            transmitters exist.
    """
    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="component_not_loaded",
        )

    entities = list(component.entities)
    if not entities:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="no_transmitters",
        )

    return [
        entity.entity_id
        for entity in entities
        if entity.supports_modulation(modulation)
        and entity.supports_frequency(frequency)
    ]


async def async_send_command(
    hass: HomeAssistant,
    entity_id_or_uuid: str,
    command: RadioFrequencyCommand,
    context: Context | None = None,
) -> None:
    """Send an RF command to the specified radio_frequency entity.

    Raises:
        vol.Invalid: If `entity_id_or_uuid` is not a valid entity ID or known entity
            registry UUID.
        HomeAssistantError: If the radio_frequency component is not loaded or the
            resolved entity is not found.
    """
    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="component_not_loaded",
        )

    ent_reg = er.async_get(hass)
    entity_id = er.async_validate_entity_id(ent_reg, entity_id_or_uuid)
    entity = component.get_entity(entity_id)
    if entity is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="entity_not_found",
            translation_placeholders={"entity_id": entity_id},
        )

    if not entity.supports_frequency(command.frequency):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="unsupported_frequency",
            translation_placeholders={
                "entity_id": entity_id,
                "frequency": str(command.frequency),
            },
        )

    if not entity.supports_modulation(command.modulation):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="unsupported_modulation",
            translation_placeholders={
                "entity_id": entity_id,
                "modulation": command.modulation,
            },
        )

    if context is not None:
        entity.async_set_context(context)

    await entity.async_send_command_internal(command)


class RadioFrequencyTransmitterEntityDescription(
    EntityDescription, frozen_or_thawed=True
):
    """Describes radio frequency transmitter entities."""


class RadioFrequencyTransmitterEntity(RestoreEntity):
    """Base class for radio frequency transmitter entities."""

    entity_description: RadioFrequencyTransmitterEntityDescription
    _attr_should_poll = False
    _attr_state: None = None

    __last_command_sent: str | None = None

    @property
    @abstractmethod
    def supported_frequency_ranges(self) -> list[tuple[int, int]]:
        """Return list of (min_hz, max_hz) tuples."""

    @callback
    @final
    def supports_frequency(self, frequency: int) -> bool:
        """Return whether the transmitter supports the given frequency."""
        return any(
            low <= frequency <= high for low, high in self.supported_frequency_ranges
        )

    @callback
    @final
    def supports_modulation(self, modulation: ModulationType) -> bool:
        """Return whether the transmitter supports the given modulation."""
        return modulation == ModulationType.OOK

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        return self.__last_command_sent

    @final
    async def async_send_command_internal(self, command: RadioFrequencyCommand) -> None:
        """Send an RF command and update state.

        Should not be overridden, handles setting last sent timestamp.
        """
        await self.async_send_command(command)
        self.__last_command_sent = dt_util.utcnow().isoformat(timespec="milliseconds")
        self.async_write_ha_state()

    @final
    async def async_internal_added_to_hass(self) -> None:
        """Call when the radio frequency entity is added to hass."""
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state not in (STATE_UNAVAILABLE, None):
            self.__last_command_sent = state.state

    @abstractmethod
    async def async_send_command(self, command: RadioFrequencyCommand) -> None:
        """Send an RF command.

        Args:
            command: The RF command to send.

        Raises:
            HomeAssistantError: If transmission fails.
        """
