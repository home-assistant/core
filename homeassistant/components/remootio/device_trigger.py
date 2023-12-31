"""Provides device automations for Remootio."""
from __future__ import annotations

import logging

from aioremootio import EventType
import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import CONF_SERIAL_NUMBER, DOMAIN, EVENT_TYPE

_LOGGER = logging.getLogger(__name__)

TRIGGER_TYPES = {EventType.LEFT_OPEN.name.lower()}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
        vol.Required(CONF_SERIAL_NUMBER): vol.All(vol.Coerce(str), vol.Length(min=1)),
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for a Remootio device."""

    _LOGGER.debug("Doing async_get_triggers with device id %s", device_id)

    triggers: list[dict[str, str]] = []

    registry: er.EntityRegistry = er.async_get(hass)

    for entry in er.async_entries_for_device(registry, device_id):
        _LOGGER.debug("Entry for device with id %s: %s", device_id, entry)

        if entry.domain != DOMAIN:
            continue

        base_trigger: dict = {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.entity_id,
            CONF_UNIQUE_ID: entry.unique_id,
            CONF_SERIAL_NUMBER: entry.unique_id,
        }

        triggers += [
            {
                **base_trigger,
                CONF_TYPE: trigger_type,
            }
            for trigger_type in TRIGGER_TYPES
        ]

    _LOGGER.debug("Triggers for device with id %s: %s", device_id, triggers)
    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""

    _LOGGER.debug(
        "Doing async_attach_trigger. config [%s] action [%s] trigger_info [%s]",
        config,
        action,
        trigger_info,
    )

    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: EVENT_TYPE,
            event_trigger.CONF_EVENT_DATA: {
                CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                CONF_TYPE: config[CONF_TYPE],
                CONF_ENTITY_ID: config[CONF_ENTITY_ID],
                CONF_UNIQUE_ID: config[CONF_UNIQUE_ID],
                CONF_SERIAL_NUMBER: config[CONF_SERIAL_NUMBER],
            },
        }
    )

    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
