"""Support for MyChevy sensors."""


from homeassistant.components import mychevy


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the MyChevy sensors."""
    if discovery_info is None:
        return

    hub = hass.data[mychevy.DOMAIN]
    hub.register_add_devices(add_devices)

    return True
