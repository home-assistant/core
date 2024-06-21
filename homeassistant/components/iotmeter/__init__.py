import logging
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import IotMeterDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

'''SERVICE_SET_CHARGING_CURRENT = 'set_charging_current'
ATTR_CURRENT = 'current'

SET_CHARGING_CURRENT_SCHEMA = vol.Schema({
    vol.Required('entity_id'): cv.entity_id,
    vol.Required(ATTR_CURRENT): vol.Coerce(int),
})
'''


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IoTMeter from a config entry."""
    _LOGGER.debug("Setting up IoTMeter integration.")
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}  # Ensure that the domain is a dictionary

    ip_address = entry.data.get("ip_address")
    port = entry.data.get("port", 8000)  # Default to port 8000 if not set

    try:
        _coordinator = IotMeterDataUpdateCoordinator(hass, ip_address, port)
        await _coordinator.async_config_entry_first_refresh()

        hass.data[DOMAIN] = {
            "coordinator": _coordinator,
            "ip_address": ip_address,
            "port": port
        }

        _LOGGER.debug("Forwarding entry setup for sensor platform.")
        await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "number"])
        entry.async_on_unload(entry.add_update_listener(update_listener))

        # Register the service
        '''
        async def async_set_charging_current(service_call: ServiceCall):
            entity_id = service_call.data['entity_id']
            current = service_call.data[ATTR_CURRENT]
            entity = hass.states.get(entity_id)
            _LOGGER.debug(f"Service called for entity {entity_id} with current {current}.")
            if entity and hasattr(entity, 'async_set_native_value'):
                await entity.async_set_native_value(current)
                _LOGGER.debug(f"Set charging current to {current}")
            else:
                _LOGGER.error(f"Entity {entity_id} does not have 'async_set_native_value' method")

        hass.services.async_register(
            DOMAIN, SERVICE_SET_CHARGING_CURRENT, async_set_charging_current, schema=SET_CHARGING_CURRENT_SCHEMA
        )
        _LOGGER.debug("Service registered successfully.")
        '''
        return True
    except Exception as e:
        _LOGGER.error(f"Error setting up IoTMeter integration: {e}")
        return False


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    ip_address = entry.data.get("ip_address", entry.data.get("ip_address"))
    port = entry.data.get("port", entry.data.get("port", 8000))
    _coordinator = hass.data[DOMAIN]["coordinator"]
    _coordinator.update_ip_port(ip_address, port)
    await _coordinator.async_request_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle unloading of an entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor", "number"])
    if unload_ok:
        hass.data.pop(DOMAIN)
    return unload_ok
