"""Provides device automations for Device Tracker."""

from operator import attrgetter
from typing import Final

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.zone import DOMAIN as ZONE_DOMAIN, trigger as zone
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_EVENT,
    CONF_OPTIONS,
    CONF_PLATFORM,
    CONF_TYPE,
    CONF_ZONE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.trigger import (
    TriggerActionType,
    TriggerInfo,
    #  protected, but only used for legacy triggers
    _async_attach_trigger_cls,
)
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

TRIGGER_TYPES: Final[set[str]] = {"enters", "leaves"}

TRIGGER_SCHEMA: Final = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
        vol.Required(CONF_ZONE): cv.entity_domain(ZONE_DOMAIN),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for Device Tracker devices."""
    registry = er.async_get(hass)
    triggers = []

    # Get all the integrations entities for this device
    for entry in er.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.id,
                CONF_TYPE: "enters",
            }
        )
        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.id,
                CONF_TYPE: "leaves",
            }
        )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    if config[CONF_TYPE] == "enters":
        event = zone.EVENT_ENTER
    else:
        event = zone.EVENT_LEAVE
    zone_config = await zone.LegacyZoneTrigger.async_validate_config(
        hass,
        {
            CONF_OPTIONS: {
                CONF_ENTITY_ID: [config[CONF_ENTITY_ID]],
                CONF_ZONE: config[CONF_ZONE],
                CONF_EVENT: event,
            }
        },
    )
    return await _async_attach_trigger_cls(
        hass, zone.LegacyZoneTrigger, "device", zone_config, action, trigger_info
    )


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List trigger capabilities."""
    zones = {
        ent.entity_id: ent.name
        for ent in sorted(hass.states.async_all(ZONE_DOMAIN), key=attrgetter("name"))
    }
    return {
        "extra_fields": vol.Schema(
            {
                vol.Required(CONF_ZONE): vol.In(zones),
            }
        )
    }
