"""Services for the Portainer integration."""

import datetime

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN, ENDPOINT_ID

ATTR_DATE_UNTIL = "until"
ATTR_DANGLING = "dangling"

SERVICE_PRUNE_IMAGES = "prune_images"
SERVICE_PRUNE_IMAGES_SCHEMA = vol.Schema(
    {
        vol.Required(ENDPOINT_ID): str,  # Expand this with a list of known edpoint IDs
        vol.Optional(ATTR_DATE_UNTIL): datetime.timedelta | None,
        vol.Optional(ATTR_DANGLING): bool | None,
    },
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_PRUNE_IMAGES,
        prune_images,
        SERVICE_PRUNE_IMAGES_SCHEMA,
    )


async def prune_images(call: ServiceCall) -> None:
    """Prune unused images in Portainer, with more controls."""
