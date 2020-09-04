"""Support for Renault devices."""
import voluptuous as vol

from .const import CONF_KAMEREON_ACCOUNT_ID, DOMAIN, SUPPORTED_PLATFORMS
from .pyzeproxy import PyzeProxy

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({}, extra=vol.ALLOW_EXTRA)}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass, config):
    """Old way of setting up integrations."""
    return True


async def async_setup_entry(hass, config_entry):
    """Load a config entry."""
    hass.data.setdefault(DOMAIN, {})

    pyzeproxy = PyzeProxy(hass, config_entry.data)
    if not await pyzeproxy.setup(True):
        return False

    if config_entry.unique_id is None:
        hass.config_entries.async_update_entry(
            config_entry, unique_id=config_entry.data[CONF_KAMEREON_ACCOUNT_ID]
        )
    hass.data[DOMAIN][config_entry.unique_id] = pyzeproxy

    for component in SUPPORTED_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = True

    for component in SUPPORTED_PLATFORMS:
        unload_ok = unload_ok and await hass.config_entries.async_forward_entry_unload(
            config_entry, component
        )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.unique_id)

    return unload_ok
