"""Services for Fritz integration."""
import logging

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import async_get as async_get_dev_reg
from homeassistant.helpers.entity_registry import async_get as async_get_ent_reg

from .const import DOMAIN, FRITZ_SERVICES, SERVICE_REBOOT, SERVICE_RECONNECT

_LOGGER = logging.getLogger(__name__)


async def async_setup_services(hass):
    """Set up services for Fritz integration."""
    if hass.data.get(FRITZ_SERVICES, False):
        return

    hass.data[FRITZ_SERVICES] = True

    async def async_call_fritz_service(service_call):
        """Call correct Fritz service."""
        fritz_tools = await _async_get_configured_fritz_tools(hass, service_call.data)

        _LOGGER.debug("Executing service %s", service_call.service)
        await fritz_tools.service_fritzbox(service_call.service)

    for service in [SERVICE_REBOOT, SERVICE_RECONNECT]:
        hass.services.async_register(DOMAIN, service, async_call_fritz_service)


async def _async_get_configured_fritz_tools(hass, data):
    """Get FritzBoxTools class from config entry."""

    entity_id = data.get("entity_id")
    device_id = data.get("device_id")

    if not entity_id and not device_id:
        raise HomeAssistantError("Missing entity or device")

    if entity_id:
        try:
            config_entry = (
                async_get_ent_reg(hass).async_get(entity_id[0]).config_entry_id
            )
        except Exception as ex:  # pylint: disable=broad-except
            raise HomeAssistantError("Specified FRITZ entity not found") from ex

    if device_id:
        try:
            config_entry = list(
                async_get_dev_reg(hass).async_get(device_id[0]).config_entries
            )[0]
        except Exception as ex:  # pylint: disable=broad-except
            raise HomeAssistantError("Specified FRITZ!Box device not found") from ex

    return hass.data[DOMAIN].get(config_entry)


async def async_unload_services(hass):
    """Unload services for Fritz integration."""

    if not hass.data.get(FRITZ_SERVICES):
        return

    hass.data[FRITZ_SERVICES] = False

    hass.services.async_remove(DOMAIN, SERVICE_REBOOT)
    hass.services.async_remove(DOMAIN, SERVICE_RECONNECT)
