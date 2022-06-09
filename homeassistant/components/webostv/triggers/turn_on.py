"""webOS Smart TV device turn on trigger."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.automation import (
    AutomationActionType,
    AutomationTriggerInfo,
)
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from ..const import DOMAIN
from ..helpers import (
    async_get_client_wrapper_by_device_entry,
    async_get_device_entry_by_device_id,
    async_get_device_id_from_entity_id,
)

# Platform type should be <DOMAIN>.<SUBMODULE_NAME>
PLATFORM_TYPE = f"{DOMAIN}.{__name__.rsplit('.', maxsplit=1)[-1]}"

TRIGGER_TYPE_TURN_ON = "turn_on"

TRIGGER_SCHEMA = vol.All(
    cv.TRIGGER_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_PLATFORM): PLATFORM_TYPE,
            vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        },
    ),
    cv.has_at_least_one_key(ATTR_ENTITY_ID, ATTR_DEVICE_ID),
)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: AutomationTriggerInfo,
    *,
    platform_type: str = PLATFORM_TYPE,
) -> CALLBACK_TYPE | None:
    """Attach a trigger."""
    device_ids = set()
    if ATTR_DEVICE_ID in config:
        device_ids.update(config.get(ATTR_DEVICE_ID, []))

    if ATTR_ENTITY_ID in config:
        device_ids.update(
            {
                async_get_device_id_from_entity_id(hass, entity_id)
                for entity_id in config.get(ATTR_ENTITY_ID, [])
            }
        )

    trigger_data = automation_info["trigger_data"]

    unsubs = []

    for device_id in device_ids:
        device = async_get_device_entry_by_device_id(hass, device_id)
        device_name = device.name_by_user or device.name

        variables = {
            **trigger_data,
            CONF_PLATFORM: platform_type,
            ATTR_DEVICE_ID: device_id,
            "description": f"webostv turn on trigger for {device_name}",
        }

        client_wrapper = async_get_client_wrapper_by_device_entry(hass, device)

        unsubs.append(
            client_wrapper.turn_on.async_attach(action, {"trigger": variables})
        )

    @callback
    def async_remove() -> None:
        """Remove state listeners async."""
        for unsub in unsubs:
            unsub()
        unsubs.clear()

    return async_remove
