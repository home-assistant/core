"""Services for Fritz integration."""
import logging

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import DOMAIN, FRITZ_SERVICES, SERVICE_REBOOT, SERVICE_RECONNECT

_LOGGER = logging.getLogger(__name__)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Fritz integration."""

    for service in (SERVICE_REBOOT, SERVICE_RECONNECT):
        if hass.services.has_service(DOMAIN, service):
            return

    async def async_call_fritz_service(service_call: ServiceCall) -> None:
        """Call correct Fritz service."""

        if not (
            fritzbox_entry_ids := await _async_get_configured_fritz_tools(
                hass, service_call
            )
        ):
            raise HomeAssistantError(
                f"Failed to call service '{service_call.service}'. Config entry for target not found"
            )

        for entry in fritzbox_entry_ids:
            _LOGGER.debug("Executing service %s", service_call.service)
            fritz_tools = hass.data[DOMAIN][entry]
            await fritz_tools.service_fritzbox(service_call.service)

    for service in (SERVICE_REBOOT, SERVICE_RECONNECT):
        hass.services.async_register(DOMAIN, service, async_call_fritz_service)


async def _async_get_configured_fritz_tools(
    hass: HomeAssistant, service_call: ServiceCall
) -> list:
    """Get FritzBoxTools class from config entry."""

    list_entry_id: list = []
    for entry_id in await async_extract_config_entry_ids(hass, service_call):
        config_entry = hass.config_entries.async_get_entry(entry_id)
        if config_entry and config_entry.domain == DOMAIN:
            list_entry_id.append(entry_id)
    return list_entry_id


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services for Fritz integration."""

    if not hass.data.get(FRITZ_SERVICES):
        return

    hass.data[FRITZ_SERVICES] = False

    hass.services.async_remove(DOMAIN, SERVICE_REBOOT)
    hass.services.async_remove(DOMAIN, SERVICE_RECONNECT)
