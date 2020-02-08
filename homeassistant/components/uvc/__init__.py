"""The uvc component."""

DOMAIN = "uvc"

CONF_NVR = "nvr"
CONF_KEY = "key"
CONF_PORT = "port"
CONF_SSL = "ssl"

DEFAULT_PORT = 7080
DEFAULT_SSL = False


async def async_setup(hass, config):
    """Set up component."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up component entry."""
    hass.async_add_job(
        hass.config_entries.async_forward_entry_setup(config_entry, "camera")
    )
    return True
