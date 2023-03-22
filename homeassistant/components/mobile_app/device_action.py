"""Provides device actions for Mobile App."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components import notify
from homeassistant.components.device_automation import InvalidDeviceAutomationConfig
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import DOMAIN
from .util import get_notify_service, supports_push, webhook_id_from_device_id

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "notify",
        vol.Required(notify.ATTR_MESSAGE): cv.template,
        vol.Optional(notify.ATTR_TITLE): cv.template,
        vol.Optional(notify.ATTR_DATA): cv.template_complex,
    }
)


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device actions for Mobile App devices."""
    webhook_id = webhook_id_from_device_id(hass, device_id)

    if webhook_id is None or not supports_push(hass, webhook_id):
        return []

    return [{CONF_DEVICE_ID: device_id, CONF_DOMAIN: DOMAIN, CONF_TYPE: "notify"}]


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Execute a device action."""
    webhook_id = webhook_id_from_device_id(hass, config[CONF_DEVICE_ID])

    if webhook_id is None:
        raise InvalidDeviceAutomationConfig(
            "Unable to resolve webhook ID from the device ID"
        )

    if (service_name := get_notify_service(hass, webhook_id)) is None:
        raise InvalidDeviceAutomationConfig(
            "Unable to find notify service for webhook ID"
        )

    service_data = {notify.ATTR_TARGET: webhook_id}

    # Render it here because we have access to variables here.
    for key in (notify.ATTR_MESSAGE, notify.ATTR_TITLE, notify.ATTR_DATA):
        if key not in config:
            continue

        value_template = config[key]
        template.attach(hass, value_template)

        try:
            service_data[key] = template.render_complex(value_template, variables)
        except TemplateError as err:
            raise InvalidDeviceAutomationConfig(
                f"Error rendering {key}: {err}"
            ) from err

    await hass.services.async_call(
        notify.DOMAIN, service_name, service_data, blocking=True, context=context
    )


async def async_get_action_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List action capabilities."""
    if config[CONF_TYPE] != "notify":
        return {}

    return {
        "extra_fields": vol.Schema(
            {
                vol.Required(notify.ATTR_MESSAGE): str,
                vol.Optional(notify.ATTR_TITLE): str,
            }
        )
    }
