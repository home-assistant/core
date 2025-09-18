"""LG Netcast TV device turn on trigger."""

import voluptuous as vol

from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.trigger import (
    PluggableAction,
    TriggerActionType,
    TriggerInfo,
)
from homeassistant.helpers.typing import ConfigType

from ..const import DOMAIN
from ..helpers import async_get_device_entry_by_device_id

PLATFORM_TYPE = f"{DOMAIN}.{__name__.rsplit('.', maxsplit=1)[-1]}"

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


def async_get_turn_on_trigger(device_id: str) -> dict[str, str]:
    """Return data for a turn on trigger."""

    return {
        CONF_PLATFORM: "device",
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
        CONF_TYPE: PLATFORM_TYPE,
    }


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
    *,
    platform_type: str = PLATFORM_TYPE,
) -> CALLBACK_TYPE | None:
    """Attach a trigger."""
    device_ids = set()
    if ATTR_DEVICE_ID in config:
        device_ids.update(config.get(ATTR_DEVICE_ID, []))

    if ATTR_ENTITY_ID in config:
        ent_reg = er.async_get(hass)

        def _get_device_id_from_entity_id(entity_id):
            entity_entry = ent_reg.async_get(entity_id)

            if (
                entity_entry is None
                or entity_entry.device_id is None
                or entity_entry.platform != DOMAIN
            ):
                raise ValueError(f"Entity {entity_id} is not a valid {DOMAIN} entity.")

            return entity_entry.device_id

        device_ids.update(
            {
                _get_device_id_from_entity_id(entity_id)
                for entity_id in config.get(ATTR_ENTITY_ID, [])
            }
        )

    trigger_data = trigger_info["trigger_data"]

    unsubs = []

    for device_id in device_ids:
        device = async_get_device_entry_by_device_id(hass, device_id)
        device_name = device.name_by_user or device.name

        variables = {
            **trigger_data,
            CONF_PLATFORM: platform_type,
            ATTR_DEVICE_ID: device_id,
            "description": f"lg netcast turn on trigger for {device_name}",
        }

        turn_on_trigger = async_get_turn_on_trigger(device_id)

        unsubs.append(
            PluggableAction.async_attach_trigger(
                hass, turn_on_trigger, action, {"trigger": variables}
            )
        )

    @callback
    def async_remove() -> None:
        """Remove state listeners async."""
        for unsub in unsubs:
            unsub()
        unsubs.clear()

    return async_remove
