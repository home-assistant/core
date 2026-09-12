"""Support for the Abode Security System."""

from typing import TYPE_CHECKING

from jaraco.abode.exceptions import Exception as AbodeException
import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import DOMAIN

if TYPE_CHECKING:
    from . import AbodeConfigEntry, AbodeSystem

ATTR_SETTING = "setting"
ATTR_VALUE = "value"


CHANGE_SETTING_SCHEMA = vol.Schema(
    {vol.Required(ATTR_SETTING): cv.string, vol.Required(ATTR_VALUE): cv.string}
)

CAPTURE_IMAGE_SCHEMA = vol.Schema({ATTR_ENTITY_ID: cv.entity_ids})

AUTOMATION_SCHEMA = vol.Schema({ATTR_ENTITY_ID: cv.entity_ids})


def _get_abode_system(hass: HomeAssistant) -> AbodeSystem:
    """Return the Abode system for the loaded config entry."""
    entry: AbodeConfigEntry = service.async_get_config_entry(hass, DOMAIN, None)
    return entry.runtime_data


def _change_setting(call: ServiceCall) -> None:
    """Change an Abode system setting."""
    setting = call.data[ATTR_SETTING]
    value = call.data[ATTR_VALUE]

    try:
        _get_abode_system(call.hass).abode.set_setting(setting, value)
    except AbodeException as ex:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="change_setting_failed",
            translation_placeholders={"error": str(ex)},
        ) from ex


def _capture_image(call: ServiceCall) -> None:
    """Capture a new image."""
    entity_ids = call.data[ATTR_ENTITY_ID]

    target_entities = [
        entity_id
        for entity_id in _get_abode_system(call.hass).entity_ids
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
        for entity_id in _get_abode_system(call.hass).entity_ids
        if entity_id in entity_ids
    ]

    for entity_id in target_entities:
        signal = f"abode_trigger_automation_{entity_id}"
        dispatcher_send(call.hass, signal)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Home Assistant services."""

    hass.services.async_register(
        DOMAIN, "change_setting", _change_setting, schema=CHANGE_SETTING_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, "capture_image", _capture_image, schema=CAPTURE_IMAGE_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, "trigger_automation", _trigger_automation, schema=AUTOMATION_SCHEMA
    )
