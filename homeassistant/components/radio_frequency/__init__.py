"""Provides functionality to interact with radio frequency devices."""

from datetime import timedelta
import logging

from rf_protocols import ModulationType, RadioFrequencyCommand

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import DATA_COMPONENT, DOMAIN
from .entity import (
    RadioFrequencyTransmitterEntity,
    RadioFrequencyTransmitterEntityDescription,
)
from .helpers import RadioFrequencyTransmitterConsumerEntity, async_send_command

__all__ = [
    "DATA_COMPONENT",
    "DOMAIN",
    "ModulationType",
    "RadioFrequencyCommand",
    "RadioFrequencyTransmitterConsumerEntity",
    "RadioFrequencyTransmitterEntity",
    "RadioFrequencyTransmitterEntityDescription",
    "async_get_transmitters",
    "async_send_command",
]

_LOGGER = logging.getLogger(__name__)

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

    websocket_api.async_setup(hass)

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
