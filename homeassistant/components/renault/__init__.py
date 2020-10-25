"""Support for Renault devices."""
from .const import DOMAIN, SUPPORTED_PLATFORMS
from .pyze_proxy import PyZEProxy


async def async_setup(hass, config):
    """Set up renault integrations."""
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass, config_entry):
    """Load a config entry."""
    pyzeproxy = PyZEProxy(hass)
    pyzeproxy.set_api_keys(config_entry.data)
    if not await pyzeproxy.attempt_login(config_entry.data):
        return False

    await pyzeproxy.initialise(config_entry.data)

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
