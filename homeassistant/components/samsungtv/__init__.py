"""The samsungtv component."""
from homeassistant.const import CONF_ID, CONF_IP_ADDRESS
from homeassistant.helpers import device_registry as dr

from .const import CONF_MANUFACTURER, CONF_MODEL, DOMAIN, LOGGER


async def async_setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""

    # def handle_send_key(call):
    #    """Handle the service call."""
    #    name = call.data.get(ATTR_NAME, DEFAULT_NAME)

    # hass.services.register(DOMAIN, 'send_key', handle_send_key)

    # Return boolean to indicate that initialization was successful.
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


async def async_unload_entry(hass, entry):
    """Unload Samsung TV entry."""
    LOGGER.error("unload entry: %s", entry)


async def async_remove_entry(hass, entry) -> None:
    """Remove Samsung TV entry."""
    LOGGER.error("remove entry: %s", entry)
