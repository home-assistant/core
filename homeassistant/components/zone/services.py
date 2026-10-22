"""Services for the zone integration."""

import probatio

from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import service

from .const import DATA_ZONE, DOMAIN

RELOAD_SERVICE_SCHEMA = probatio.Schema({})


async def _async_reload_service(service_call: ServiceCall) -> None:
    """Remove all zones and load new ones from config."""
    data = service_call.hass.data[DATA_ZONE]
    conf = await data.component.async_prepare_reload(skip_reset=True)
    await data.yaml_collection.async_load(conf[DOMAIN])


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the zone services."""
    service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        _async_reload_service,
        schema=RELOAD_SERVICE_SCHEMA,
    )
