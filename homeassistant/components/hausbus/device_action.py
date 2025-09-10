import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er

DOMAIN = "hausbus"

_LOGGER = logging.getLogger(__name__)

ACTION_SCHEMA = vol.Schema(
    {
        vol.Required("domain"): DOMAIN,
        vol.Required("type"): cv.string,
        vol.Required("device_id"): cv.string,
        vol.Required("entity_id"): cv.entity_id,
    },
    extra=vol.ALLOW_EXTRA,
)


# ----------------------------
# Actions für ein Device holen
# ----------------------------
async def async_get_actions(hass: HomeAssistant, device_id: str):
    """Liefert Actions für ein Device"""

    actions = []

    registry = er.async_get(hass)
    entities = [ent for ent in registry.entities.values() if ent.device_id == device_id]
    _LOGGER.debug(f"entities for {device_id} returns {entities}")
    for ent in entities:
        if DOMAIN in ent.options:
            hausbus_type = ent.options[DOMAIN].get("hausbus_type")
            hausbus_special_type = ent.options[DOMAIN].get("hausbus_special_type")
            name = ent.name or ent.original_name

            _LOGGER.debug(
                f"{name} is type {hausbus_type} special_type {hausbus_special_type}"
            )

            if hausbus_type == "HausbusDimmerLight":
                addAction(
                    "dimmer_set_brightness", name, device_id, ent.entity_id, actions
                )
                addAction("dimmer_start_ramp", name, device_id, ent.entity_id, actions)
                addAction("dimmer_stop_ramp", name, device_id, ent.entity_id, actions)
            elif hausbus_type == "HausbusRGBDimmerLight":
                addAction("rgb_set_color", name, device_id, ent.entity_id, actions)
            elif hausbus_type == "HausbusLedLight":
                addAction("led_off", name, device_id, ent.entity_id, actions)
                addAction("led_on", name, device_id, ent.entity_id, actions)
                addAction("led_blink", name, device_id, ent.entity_id, actions)
                addAction(
                    "led_set_min_brightness", name, device_id, ent.entity_id, actions
                )
            elif hausbus_type == "HausbusSwitch":
                addAction("switch_off", name, device_id, ent.entity_id, actions)
                addAction("switch_on", name, device_id, ent.entity_id, actions)
                addAction("switch_toggle", name, device_id, ent.entity_id, actions)
            elif hausbus_type == "HausbusCover":
                addAction("cover_toggle", name, device_id, ent.entity_id, actions)
            elif (
                hausbus_type == "HausbusEvent" or hausbus_type == "HausbusBinarySensor"
            ):
                addAction(
                    "push_button_configure_events",
                    name,
                    device_id,
                    ent.entity_id,
                    actions,
                )

            # if hausbus_special_type == 1:
            #  addAction("ssr_control", name, device_id, ent.entity_id, actions)

    _LOGGER.debug(f"async_get_actions for {device_id} returns {actions}")
    return actions


def addAction(
    actionName: str,
    entityName: str,
    device_id: str,
    entity_id: str,
    actions: list[dict],
):
    actions.append(
        {
            "domain": DOMAIN,
            "type": f"{actionName} {entityName}",
            "device_id": device_id,
            "entity_id": entity_id,
        }
    )


# ----------------------------
# Action ausführen
# ----------------------------
async def async_call_action_from_config(
    hass: HomeAssistant, config: dict[str, Any], variables: dict[str, Any], context
) -> None:

    service = config["type"].partition(" ")[0]
    service_data = {
        k: v for k, v in config.items() if k not in ("domain", "type", "device_id")
    }
    _LOGGER.debug("Rufe Service hausbus.%s mit %s", service, service_data)
    await hass.services.async_call(DOMAIN, service, service_data, context=context)


# ----------------------------
# Action-Capabilities
# ----------------------------
async def async_get_action_capabilities(hass: HomeAssistant, config: dict[str, Any]):

    service_type = config["type"]
    _LOGGER.debug(f"async_get_action_capabilities {service_type}")

    result = {}

    registry = er.async_get(hass)
    entity = registry.entities.get(config["entity_id"])
    _LOGGER.debug(f"entity {entity} {entity.options}")

    if entity and DOMAIN in entity.options:
        hausbus_type = entity.options[DOMAIN].get("hausbus_type")
        hausbus_special_type = entity.options[DOMAIN].get("hausbus_special_type")

        _LOGGER.debug(
            f"hausbus_type {hausbus_type} hausbus_special_type {hausbus_special_type}"
        )

        if hausbus_type == "HausbusDimmerLight":
            if service_type.startswith("dimmer_set_brightness"):
                SCHEMA = vol.Schema(
                    {
                        vol.Required("brightness", default=100): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=100)
                        ),
                        vol.Optional("duration", default=0): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=65535)
                        ),
                    }
                )
            elif service_type.startswith("dimmer_start_ramp"):
                SCHEMA = vol.Schema(
                    {
                        vol.Required("direction", default="up"): vol.In(
                            ["up", "down", "toggle"]
                        )
                    }
                )
            elif service_type.startswith("dimmer_stop_ramp"):
                SCHEMA = vol.Schema({})
            result = {"extra_fields": SCHEMA}
        elif hausbus_type == "HausbusRGBDimmerLight":
            if service_type.startswith("rgb_set_color"):
                SCHEMA = vol.Schema(
                    {
                        vol.Required("brightness_red", default=100): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=100)
                        ),
                        vol.Required("brightness_green", default=100): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=100)
                        ),
                        vol.Required("brightness_blue", default=100): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=100)
                        ),
                        vol.Optional("duration", default=0): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=65535)
                        ),
                    }
                )
            elif service_type.startswith("dimmer_start_ramp"):
                SCHEMA = vol.Schema(
                    {
                        vol.Required("direction", default="up"): vol.In(
                            ["up", "down", "toggle"]
                        )
                    }
                )
            elif service_type.startswith("dimmer_stop_ramp"):
                SCHEMA = vol.Schema({})
            result = {"extra_fields": SCHEMA}
        elif hausbus_type == "HausbusLedLight":
            if service_type.startswith("led_off"):
                SCHEMA = vol.Schema(
                    {
                        vol.Required("offDelay", default=0): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=65535)
                        ),
                    }
                )
            elif service_type.startswith("led_on"):
                SCHEMA = vol.Schema(
                    {
                        vol.Required("brightness", default=100): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=100)
                        ),
                        vol.Required("duration", default=0): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=65535)
                        ),
                        vol.Optional("onDelay", default=0): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=65535)
                        ),
                    }
                )
            elif service_type.startswith("led_blink"):
                SCHEMA = vol.Schema(
                    {
                        vol.Required("brightness", default=100): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=100)
                        ),
                        vol.Required("offTime", default=1): vol.All(
                            vol.Coerce(int), vol.Range(min=1, max=255)
                        ),
                        vol.Optional("onTime", default=1): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=255)
                        ),
                        vol.Optional("quantity", default=0): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=65535)
                        ),
                    }
                )
            elif service_type.startswith("led_set_min_brightness"):
                SCHEMA = vol.Schema(
                    {
                        vol.Required("minBrightness", default=0): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=100)
                        ),
                    }
                )
        elif hausbus_type == "HausbusSwitch":
            if service_type.startswith("switch_off"):
                SCHEMA = vol.Schema(
                    {
                        vol.Required("offDelay", default=0): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=65535)
                        ),
                    }
                )
            elif service_type.startswith("switch_on"):
                SCHEMA = vol.Schema(
                    {
                        vol.Required("duration", default=0): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=65535)
                        ),
                        vol.Optional("onDelay", default=0): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=65535)
                        ),
                    }
                )
            elif service_type.startswith("switch_toggle"):
                SCHEMA = vol.Schema(
                    {
                        vol.Required("offTime", default=1): vol.All(
                            vol.Coerce(int), vol.Range(min=1, max=255)
                        ),
                        vol.Required("onTime", default=1): vol.All(
                            vol.Coerce(int), vol.Range(min=1, max=255)
                        ),
                        vol.Optional("quantity", default=0): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=255)
                        ),
                    }
                )
        elif hausbus_type == "HausbusCover":
            if service_type.startswith("cover_toggle"):
                SCHEMA = vol.Schema({})
        elif hausbus_type == "HausbusEvent" or hausbus_type == "HausbusBinarySensor":
            if service_type.startswith("push_button_configure_events"):
                SCHEMA = vol.Schema(
                    {
                        vol.Required(
                            "eventActivationStatus", default="ENABLED"
                        ): vol.In(["DISABLED", "ENABLED", "INVERT"]),
                        vol.Optional("disabled_duration", default=0): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=255)
                        ),
                    }
                )

        # if hausbus_special_type==1:
        #  if service_type.startswith("ssr_control"):
        #    SCHEMA = vol.Schema({
        #      vol.Required("power", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        #    })

        result = {"extra_fields": SCHEMA}

    _LOGGER.debug(f"returns {result}")
    return result
