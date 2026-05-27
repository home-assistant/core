"""Provides functionality to interact with radio frequency devices."""

from datetime import timedelta
import logging

from rf_protocols import ModulationType, RadioFrequencyCommand

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .entity import (
    RadioFrequencyTransmitterEntity,
    RadioFrequencyTransmitterEntityDescription,
)

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
