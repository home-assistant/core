"""Services for Risco integration."""

from datetime import datetime

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, SERVICE_SET_TIME
from .models import LocalData

ATTR_CONF_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_TIME = "time"


async def async_setup_services(hass: HomeAssistant) -> None:
    """Create the Risco Services/Actions."""

    async def _set_time(service_call: ServiceCall) -> None:
        config_entry_id = service_call.data.get(ATTR_CONF_CONFIG_ENTRY_ID, None)
        time = service_call.data.get(ATTR_TIME, None)

        time_to_send = time
        if time is None:
            time_to_send = datetime.now()

        local_data: LocalData = hass.data[DOMAIN][config_entry_id]

        await local_data.system.set_time(time_to_send)

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SET_TIME,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CONF_CONFIG_ENTRY_ID): cv.string,
                vol.Optional(ATTR_TIME): cv.datetime,
            }
        ),
        service_func=_set_time,
    )
