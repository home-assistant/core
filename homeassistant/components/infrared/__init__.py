"""Provides functionality to interact with infrared devices."""

from collections.abc import Callable
from datetime import timedelta
import logging

from infrared_protocols.commands import Command as InfraredCommand
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .entity import (  # noqa: F401
    InfraredDeviceClass,
    InfraredEmitterEntity,
    InfraredEmitterEntityDescription,
    InfraredEntity,
    InfraredEntityDescription,
    InfraredReceivedSignal,
    InfraredReceiverEntity,
    InfraredReceiverEntityDescription,
)

__all__ = [
    "DOMAIN",
    "InfraredEmitterEntity",
    "InfraredEmitterEntityDescription",
    "InfraredEntity",
    "InfraredEntityDescription",
    "InfraredReceivedSignal",
    "InfraredReceiverEntity",
    "InfraredReceiverEntityDescription",
    "async_get_emitters",
    "async_get_receivers",
    "async_send_command",
    "async_subscribe_receiver",
]


_LOGGER = logging.getLogger(__name__)

DATA_COMPONENT: HassKey[
    EntityComponent[InfraredEmitterEntity | InfraredReceiverEntity]
] = HassKey(DOMAIN)
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


async def async_send_command(
    hass: HomeAssistant,
    entity_id_or_uuid: str,
    command: InfraredCommand,
    context: Context | None = None,
) -> None:
    """Send an IR command to the specified infrared entity.

    Raises:
        HomeAssistantError: If the infrared entity is not found.
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
    if entity is None or not isinstance(entity, InfraredEmitterEntity):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="entity_not_found",
            translation_placeholders={"entity_id": entity_id},
        )

    if context is not None:
        entity.async_set_context(context)

    await entity.async_send_command_internal(command)


@callback
def async_subscribe_receiver(
    hass: HomeAssistant,
    entity_id_or_uuid: str,
    signal_callback: Callable[[InfraredReceivedSignal], None],
) -> CALLBACK_TYPE:
    """Subscribe to IR signals from a specific receiver entity.

    Raises:
        HomeAssistantError: If the receiver entity is not found.
    """
    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="component_not_loaded",
        )

    ent_reg = er.async_get(hass)
    try:
        entity_id = er.async_validate_entity_id(ent_reg, entity_id_or_uuid)
    except vol.Invalid as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="receiver_not_found",
            translation_placeholders={"entity_id": entity_id_or_uuid},
        ) from err

    entity = component.get_entity(entity_id)
    if entity is None or not isinstance(entity, InfraredReceiverEntity):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="receiver_not_found",
            translation_placeholders={"entity_id": entity_id},
        )

    return entity.async_subscribe_received_signal(signal_callback)
