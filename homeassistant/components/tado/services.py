"""Services for the Tado integration."""

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector, service

from .const import (
    ATTR_MESSAGE,
    CONF_CONFIG_ENTRY,
    CONF_READING,
    DOMAIN,
    SERVICE_ADD_METER_READING,
)
from .coordinator import TadoConfigEntry

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


async def _add_meter_reading(call: ServiceCall) -> None:
    """Send meter reading to Tado."""
    reading: int = call.data[CONF_READING]
    _LOGGER.debug("Add meter reading %s", reading)

    entry: TadoConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[CONF_CONFIG_ENTRY]
    )

    coordinator = entry.runtime_data
    response: dict = await coordinator.set_meter_reading(call.data[CONF_READING])

    if ATTR_MESSAGE in response:
        raise HomeAssistantError(response[ATTR_MESSAGE])


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Tado integration."""

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_METER_READING, _add_meter_reading, SCHEMA_ADD_METER_READING
    )
