"""Support for Genius Hub binary_sensor devices."""
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import CONF_UID, DOMAIN, GeniusDevice

GH_STATE_ATTR = "outputOnOff"


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set up the Genius Hub sensor entities."""
    if discovery_info is None:
        return

    hub = hass.data[DOMAIN]["client"]
    uid = hub.uid if hub.uid else hass.data[DOMAIN][CONF_UID]

    switches = [
        GeniusBinarySensor(uid, d, GH_STATE_ATTR)
        for d in hub.device_objs
        if GH_STATE_ATTR in d.data["state"]
    ]

    async_add_entities(switches, update_before_add=True)


class GeniusBinarySensor(GeniusDevice, BinarySensorDevice):
    """Representation of a Genius Hub binary_sensor."""

    def __init__(self, uid: str, device, state_attr) -> None:
        """Initialize the binary sensor."""
        super().__init__(uid, device)

        self._state_attr = state_attr

        if device.type[:21] == "Dual Channel Receiver":
            self._name = f"{device.type[:21]} {device.id}"
        else:
            self._name = f"{device.type} {device.id}"

    @property
    def is_on(self) -> bool:
        """Return the status of the sensor."""
        return self._device.data["state"][self._state_attr]
