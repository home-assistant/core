"""Services for the Logitech Harmony Hub integration."""

import probatio

from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN, SERVICE_CHANGE_CHANNEL, SERVICE_SYNC

ATTR_CHANNEL = "channel"
HARMONY_CHANGE_CHANNEL_SCHEMA: VolDictType = {
    probatio.Required(ATTR_CHANNEL): cv.positive_int,
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Logitech Harmony Hub integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SYNC,
        entity_domain=REMOTE_DOMAIN,
        schema=None,
        func="sync",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CHANGE_CHANNEL,
        entity_domain=REMOTE_DOMAIN,
        schema=HARMONY_CHANGE_CHANNEL_SCHEMA,
        func="change_channel",
    )
