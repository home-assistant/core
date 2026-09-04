"""Support for Modbus services."""

from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.service import async_register_admin_service

from .const import DATA_MODBUS_HUBS, DOMAIN, LOGGER
from .modbus import async_modbus_setup


async def _async_reload_config(call: ServiceCall) -> None:
    """Reload Modbus."""
    hass = call.hass
    if DATA_MODBUS_HUBS not in hass.data:
        LOGGER.error("Modbus cannot reload, because it was never loaded")
        return
    hubs = hass.data[DATA_MODBUS_HUBS]
    for hub in hubs.values():
        await hub.async_close()
    reset_platforms = async_get_platforms(hass, DOMAIN)
    for reset_platform in reset_platforms:
        LOGGER.debug("Reload modbus resetting platform: %s", reset_platform.domain)
        await reset_platform.async_reset()
    reload_config = await async_integration_yaml_config(hass, DOMAIN)
    if not reload_config:
        LOGGER.debug("Modbus not present anymore")
        return
    LOGGER.debug("Modbus reloading")
    await async_modbus_setup(hass, reload_config)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Modbus services."""
    async_register_admin_service(hass, DOMAIN, SERVICE_RELOAD, _async_reload_config)
