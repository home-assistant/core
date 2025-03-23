"""Global services file."""

from functools import partial

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.service import async_set_service_schema

from .awtrix import AwtrixService
from .const import DOMAIN, SERVICE_TO_FIELDS, SERVICE_TO_SCHEMA, SERVICES


class AwtrixServicesSetup:
    """Class to handle Integration Services."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialise services."""
        self.hass = hass
        self.config_entry = config_entry

        hass.async_create_task(self.async_setup_services())

    async def async_setup_services(self):
        """Initialise the services in Hass."""

        async def service_handler(awtrixService, service, call: ServiceCall) -> None:
            """Handle service call."""

            func = getattr(awtrixService, service)
            if func:
                await func(call.data)

        awtrixService = AwtrixService(self.hass)
        for service_name in SERVICES:
            self.hass.services.async_register(
                DOMAIN,
                service_name,
                partial(service_handler, awtrixService, service_name),
                schema=SERVICE_TO_SCHEMA[service_name]
            )

            # Register the service description
            async_set_service_schema(
                self.hass,
                DOMAIN,
                service_name,
                {
                    "description": (
                        f"Calls the service {service_name} of the node AWTRIX"
                    ),
                    "fields": SERVICE_TO_FIELDS[service_name],
                },
            )
