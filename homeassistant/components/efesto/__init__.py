"""Support for Efesto heating devices."""
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN


async def async_setup(hass, config):
    """Set up the Efesto integration, nothing to do."""
    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry for Efesto."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, CLIMATE_DOMAIN)
    )

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_unload(entry, CLIMATE_DOMAIN)
    )

    return True
