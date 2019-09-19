"""Support for Genius Hub binary_sensor devices."""
from homeassistant.components.binary_sensor import BinarySensorDevice

from . import DOMAIN, GeniusDevice

GH_STATE_ATTR = "outputOnOff"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Genius Hub sensor entities."""
    if discovery_info is None:
        return

    client = hass.data[DOMAIN]["client"]

    switches = [
        GeniusBinarySensor(d, GH_STATE_ATTR)
        for d in client.device_objs
        if GH_STATE_ATTR in d.data["state"]
    ]

    async_add_entities(switches, update_before_add=True)


class GeniusBinarySensor(GeniusDevice, BinarySensorDevice):
    """Representation of a Genius Hub binary_sensor."""

    def __init__(self, device, state_attr) -> None:
        """Initialize the binary sensor."""
        super().__init__()

        self._device = device
        if device.type[:21] == "Dual Channel Receiver":  # TODO: can I rationalise this?
            self._name = f"Dual Channel Receiver {device.id}"
        else:
            self._name = f"{device.type} {device.id}"
        self._state_attr = state_attr

    @property
    def is_on(self) -> bool:
        """Return the status of the sensor."""
        return self._device.data["state"][self._state_attr]
