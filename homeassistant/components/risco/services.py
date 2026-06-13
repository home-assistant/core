"""Services for Risco integration."""

from datetime import datetime

import voluptuous as vol

from homeassistant.const import ATTR_CONFIG_ENTRY_ID, ATTR_TIME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN, SERVICE_SET_TIME
from .models import RiscoConfigEntry


async def async_setup_services(hass: HomeAssistant) -> None:
    """Create the Risco Services/Actions."""

    async def _set_time(service_call: ServiceCall) -> None:
        entry: RiscoConfigEntry = service.async_get_config_entry(
            service_call.hass, DOMAIN, service_call.data[ATTR_CONFIG_ENTRY_ID]
        )
        time = service_call.data.get(ATTR_TIME)

        # Validate config entry is local (not cloud)
        if not (local_data := entry.runtime_data.local_data):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_local_entry",
            )

        time_to_send = time
        if time is None:
            time_to_send = datetime.now()

        await local_data.system.set_time(time_to_send)

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_SET_TIME,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
                vol.Optional(ATTR_TIME): cv.datetime,
            }
        ),
        service_func=_set_time,
    )
