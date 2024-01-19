"""Services for the Tado integration."""
import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import selector

from .const import (
    ATTR_CONFIG_ENTRY,
    ATTR_MESSAGE,
    ATTR_READING,
    DATA,
    DOMAIN,
    SERVICE_ADD_METER_READING,
)

_LOGGER = logging.getLogger(__name__)
SCHEMA_ADD_METER_READING = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): selector.ConfigEntrySelector(
            {
                "integration": DOMAIN,
            }
        ),
        vol.Required(ATTR_READING, default=0): vol.Coerce(int),
    }
)


@callback
def setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Tado integration."""

    async def add_meter_reading(call: ServiceCall) -> None:
        """Send meter reading to Tado."""
        entry_id: str = call.data[ATTR_CONFIG_ENTRY]
        reading: int = call.data[ATTR_READING]
        _LOGGER.info("Add meter reading %s", reading)

        tadoconnector = hass.data[DOMAIN][entry_id][DATA]
        response: dict = await hass.async_add_executor_job(
            tadoconnector.set_meter_reading, call.data[ATTR_READING]
        )

        if ATTR_MESSAGE in response:
            raise ServiceValidationError(response[ATTR_MESSAGE])

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_METER_READING, add_meter_reading, SCHEMA_ADD_METER_READING
    )
