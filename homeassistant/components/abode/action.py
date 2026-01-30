"""Support for the Abode Security System."""

from __future__ import annotations

from jaraco.abode.exceptions import Exception as AbodeException
import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.action import Action, make_action
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import DOMAIN, DOMAIN_DATA, LOGGER

SERVICE_SETTINGS = "change_setting"
SERVICE_CAPTURE_IMAGE = "capture_image"
SERVICE_TRIGGER_AUTOMATION = "trigger_automation"

ATTR_SETTING = "setting"
ATTR_VALUE = "value"


CHANGE_SETTING_SCHEMA = vol.Schema(
    {vol.Required(ATTR_SETTING): cv.string, vol.Required(ATTR_VALUE): cv.string}
)

CAPTURE_IMAGE_SCHEMA = vol.Schema({ATTR_ENTITY_ID: cv.entity_ids})

AUTOMATION_SCHEMA = vol.Schema({ATTR_ENTITY_ID: cv.entity_ids})


def _change_setting(call: ServiceCall) -> None:
    """Change an Abode system setting."""
    setting = call.data[ATTR_SETTING]
    value = call.data[ATTR_VALUE]

    try:
        call.hass.data[DOMAIN_DATA].abode.set_setting(setting, value)
    except AbodeException as ex:
        LOGGER.warning(ex)


def _capture_image(call: ServiceCall) -> None:
    """Capture a new image."""
    entity_ids = call.data[ATTR_ENTITY_ID]

    target_entities = [
        entity_id
        for entity_id in call.hass.data[DOMAIN_DATA].entity_ids
        if entity_id in entity_ids
    ]

    for entity_id in target_entities:
        signal = f"abode_camera_capture_{entity_id}"
        dispatcher_send(call.hass, signal)


def _trigger_automation(call: ServiceCall) -> None:
    """Trigger an Abode automation."""
    entity_ids = call.data[ATTR_ENTITY_ID]

    target_entities = [
        entity_id
        for entity_id in call.hass.data[DOMAIN_DATA].entity_ids
        if entity_id in entity_ids
    ]

    for entity_id in target_entities:
        signal = f"abode_trigger_automation_{entity_id}"
        dispatcher_send(call.hass, signal)


ACTIONS = {
    SERVICE_SETTINGS: make_action(
        DOMAIN, service_func=_change_setting, schema=CHANGE_SETTING_SCHEMA
    ),
    SERVICE_CAPTURE_IMAGE: make_action(
        DOMAIN, service_func=_capture_image, schema=CAPTURE_IMAGE_SCHEMA
    ),
    SERVICE_TRIGGER_AUTOMATION: make_action(
        DOMAIN, service_func=_trigger_automation, schema=AUTOMATION_SCHEMA
    ),
}


async def async_get_actions(hass: HomeAssistant) -> dict[str, type[Action]]:
    """Return the actions provided by this integration."""
    return ACTIONS
