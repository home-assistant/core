"""Services for the Škoda integration."""

from enum import StrEnum

import probatio

from homeassistant.const import CommonServiceArgument
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import service
from homeassistant.helpers.selector import ConfigEntrySelector

from .const import DOMAIN
from .coordinator import SkodaConfigEntry


class SkodaService(StrEnum):
    """Store keys for Škoda services."""

    GET_IMAGE_URL = "get_image_url"


SERVICE_GET_IMAGE_URL_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
    }
)


async def _async_get_image_url(call: ServiceCall) -> ServiceResponse:
    """Return the URL of the vehicle render."""
    entry: SkodaConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
    )
    vehicle = entry.runtime_data.coordinator.data.vehicle_response.vehicle

    if vehicle.render_url is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="render_unavailable",
        )

    return {"url": vehicle.render_url}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Škoda integration."""
    hass.services.async_register(
        DOMAIN,
        SkodaService.GET_IMAGE_URL,
        _async_get_image_url,
        schema=SERVICE_GET_IMAGE_URL_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
