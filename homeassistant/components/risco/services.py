"""Services for Risco integration."""

from enum import StrEnum

import probatio

from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .models import RiscoConfigEntry


class RiscoService(StrEnum):
    """Store keys for Risco services."""

    SET_TIME = "set_time"


class RiscoServiceArgument(StrEnum):
    """Store keys for Risco service arguments."""

    TIME = "time"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Create the Risco Services/Actions."""

    async def _set_time(service_call: ServiceCall) -> None:
        entry: RiscoConfigEntry = service.async_get_config_entry(
            service_call.hass,
            DOMAIN,
            service_call.data[CommonServiceArgument.CONFIG_ENTRY_ID],
        )
        time = service_call.data.get(RiscoServiceArgument.TIME)

        # Validate config entry is local (not cloud)
        if not (local_data := entry.runtime_data.local_data):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_local_entry",
            )

        time_to_send = time
        if time is None:
            time_to_send = dt_util.now()

        await local_data.system.set_time(time_to_send)

    hass.services.async_register(
        domain=DOMAIN,
        service=RiscoService.SET_TIME,
        schema=probatio.Schema(
            {
                probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
                probatio.Optional(RiscoServiceArgument.TIME): cv.datetime,
            }
        ),
        service_func=_set_time,
    )
