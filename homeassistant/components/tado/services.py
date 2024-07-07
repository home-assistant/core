"""Services for the Tado integration."""

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import selector

from .const import (
    ATTR_MESSAGE,
    CONF_CONFIG_ENTRY,
    CONF_READING,
    DOMAIN,
    SERVICE_ADD_METER_READING,
)
from .tado_connector import TadoConnector

_LOGGER = logging.getLogger(__name__)
SCHEMA_ADD_METER_READING = vol.Schema(
    {
        vol.Required(CONF_CONFIG_ENTRY): selector.ConfigEntrySelector(
            {
                "integration": DOMAIN,
            }
        ),
        vol.Required(CONF_READING): vol.Coerce(int),
    }
)


@callback
def setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Tado integration."""

    async def add_meter_reading(call: ServiceCall) -> None:
        """Send meter reading to Tado."""
        entry_id: str = call.data[CONF_CONFIG_ENTRY]
        reading: int = call.data[CONF_READING]
        _LOGGER.debug("Add meter reading %s", reading)

        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            raise ServiceValidationError("Config entry not found")

        tadoconnector: TadoConnector = entry.runtime_data.tadoconnector

        response: dict = await hass.async_add_executor_job(
            tadoconnector.set_meter_reading, call.data[CONF_READING]
        )

        if ATTR_MESSAGE in response:
            raise HomeAssistantError(response[ATTR_MESSAGE])

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_METER_READING, add_meter_reading, SCHEMA_ADD_METER_READING
    )
