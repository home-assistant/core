"""Provides functionality to interact with infrared devices."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import DATA_COMPONENT, DOMAIN
from .entity import (  # noqa: F401
    InfraredCommand,
    InfraredDeviceClass,
    InfraredEmitterEntity,
    InfraredEmitterEntityDescription,
    InfraredEntity,
    InfraredEntityDescription,
    InfraredReceivedSignal,
    InfraredReceiverEntity,
    InfraredReceiverEntityDescription,
)
from .helpers import (
    InfraredEmitterConsumerEntity,
    InfraredReceiverConsumerEntity,
    async_send_command,
    async_subscribe_receiver,
)

__all__ = [
    "DOMAIN",
    "InfraredCommand",
    "InfraredEmitterConsumerEntity",
    "InfraredEmitterEntity",
    "InfraredEmitterEntityDescription",
    "InfraredEntity",
    "InfraredEntityDescription",
    "InfraredReceivedSignal",
    "InfraredReceiverConsumerEntity",
    "InfraredReceiverEntity",
    "InfraredReceiverEntityDescription",
    "async_get_emitters",
    "async_get_receivers",
    "async_send_command",
    "async_subscribe_receiver",
]


_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the infrared domain."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[
        InfraredEmitterEntity | InfraredReceiverEntity
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
def async_get_emitters(hass: HomeAssistant) -> list[str]:
    """Get all infrared emitter entity IDs."""
    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        return []

    return [
        entity.entity_id
        for entity in component.entities
        if isinstance(entity, InfraredEmitterEntity)
    ]


@callback
def async_get_receivers(hass: HomeAssistant) -> list[str]:
    """Get all infrared receiver entity IDs."""
    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        return []

    return [
        entity.entity_id
        for entity in component.entities
        if isinstance(entity, InfraredReceiverEntity)
    ]
