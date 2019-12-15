"""Get the local IP (eth0 equivalent) of the Home Assistant instance."""
import homeassistant.util as hass_util

DOMAIN = "localip"


async def async_setup(hass, config):
    """Set up the interface with the detected IP."""
    hass.states.async_set("localip.ip", hass_util.get_local_ip())

    # Return boolean to indicate that initialization was successful.
    return True
