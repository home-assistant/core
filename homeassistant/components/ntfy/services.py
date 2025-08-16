"""Actions for the ntfy integration."""

from __future__ import annotations

from datetime import timedelta

import voluptuous as vol
from yarl import URL

from homeassistant.components.notify import ATTR_MESSAGE, ATTR_TITLE
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import entity_service_call

from .const import (
    ATTR_ATTACH,
    ATTR_CALL,
    ATTR_CLICK,
    ATTR_DELAY,
    ATTR_EMAIL,
    ATTR_ICON,
    ATTR_MARKDOWN,
    ATTR_PRIORITY,
    ATTR_TAGS,
    DOMAIN,
    SERVICE_PUBLISH,
)
from .notify import async_get_entities

SERVICE_PUBLISH_SCHEMA = {
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Optional(ATTR_TITLE): cv.string,
    vol.Optional(ATTR_MESSAGE): cv.string,
    vol.Optional(ATTR_MARKDOWN): cv.boolean,
    vol.Optional(ATTR_TAGS): vol.All(cv.ensure_list, [str]),
    vol.Optional(ATTR_PRIORITY): vol.All(vol.Coerce(int), vol.Range(1, 5)),
    vol.Optional(ATTR_CLICK): vol.All(vol.Url(), vol.Coerce(URL)),
    vol.Optional(ATTR_DELAY): vol.All(
        cv.time_period,
        vol.Range(min=timedelta(seconds=10), max=timedelta(days=3)),
    ),
    vol.Optional(ATTR_ATTACH): vol.All(vol.Url(), vol.Coerce(URL)),
    vol.Optional(ATTR_EMAIL): vol.Email(),
    vol.Optional(ATTR_CALL): cv.string,
    vol.Optional(ATTR_ICON): vol.All(vol.Url(), vol.Coerce(URL)),
}


async def _publish(call: ServiceCall) -> None:
    await entity_service_call(call.hass, async_get_entities(call.hass), "publish", call)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up action for ntfy integration."""

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_PUBLISH,
        schema=cv.make_entity_service_schema(SERVICE_PUBLISH_SCHEMA),
        service_func=_publish,
    )
