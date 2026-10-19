"""Services for the rest integration."""

import contextlib

import probatio

from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.reload import (
    async_integration_yaml_config,
    async_reload_integration_platforms,
)

from .const import DOMAIN, PLATFORMS
from .util import async_process_config, async_setup_shared_data


async def _reload_service_handler(service: ServiceCall) -> None:
    """Remove all user-defined groups and load new ones from config."""
    hass = service.hass
    conf = None
    # pylint: disable-next=home-assistant-action-swallowed-exception
    with contextlib.suppress(HomeAssistantError):
        conf = await async_integration_yaml_config(hass, DOMAIN)
    if conf is None:
        return
    await async_reload_integration_platforms(hass, DOMAIN, PLATFORMS)
    async_setup_shared_data(hass)
    await async_process_config(hass, conf)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the rest services."""
    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, _reload_service_handler, schema=probatio.Schema({})
    )
