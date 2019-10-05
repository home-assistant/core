"""The Samsung TV integration."""
import voluptuous as vol

from homeassistant.const import CONF_ID, CONF_IP_ADDRESS
from homeassistant.helpers import device_registry as dr

from .const import CONF_MANUFACTURER, CONF_MODEL, DOMAIN, LOGGER


CONFIG_SCHEMA = vol.Schema({vol.Optional(DOMAIN): {}})


async def async_setup(hass, config):
    """Set up the Samsung TV integration."""
    return True

async def async_setup_entry(hass, entry):
    """Set up the Samsung TV platform."""
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, entry.data[CONF_IP_ADDRESS])},
        identifiers={(DOMAIN, entry.data[CONF_ID])},
        manufacturer=entry.data[CONF_MANUFACTURER],
        model=entry.data[CONF_MODEL],
        name=entry.title,
    )

    return True
