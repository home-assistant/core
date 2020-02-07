"""The uvc component."""
from homeassistant.const import CONF_PORT, CONF_SSL

DOMAIN = "uvc"

CONF_NVR = "nvr"
CONF_KEY = "key"
CONF_PASSWORD = "password"

DEFAULT_PASSWORD = "ubnt"
DEFAULT_PORT = 7080
DEFAULT_SSL = False


async def async_setup(hass, config):
    """Setup."""
    return True


async def async_setup_entry(hass, config_entry):
    """Entry setup."""
    hass.async_add_job(
        hass.config_entries.async_forward_entry_setup(config_entry, "camera")
    )
