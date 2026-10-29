"""Services for the command_line integration."""

from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN, LOGGER
from .helpers import async_load_platforms
from .utils import async_refresh_shell_template_issues


async def _async_reload_config(call: ServiceCall) -> None:
    """Reload Command Line."""
    hass = call.hass
    reload_config = await async_integration_yaml_config(hass, DOMAIN)
    # Set up entities keep their deprecation issue, issues of others are deleted
    with async_refresh_shell_template_issues(hass):
        reset_platforms = async_get_platforms(hass, DOMAIN)
        for reset_platform in reset_platforms:
            LOGGER.debug("Reload resetting platform: %s", reset_platform.domain)
            await reset_platform.async_reset()
        if not reload_config:
            return
        await async_load_platforms(hass, reload_config.get(DOMAIN, []), reload_config)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the command_line services."""
    async_register_admin_service(hass, DOMAIN, SERVICE_RELOAD, _async_reload_config)
