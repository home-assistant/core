"""Support for Genius Hub binary_sensor devices."""
from typing import Any, Dict

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.util.dt import utc_from_timestamp

from . import DOMAIN, GeniusEntity

GH_IS_SWITCH = ["Dual Channel Receiver", "Electric Switch", "Smart Plug"]


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Genius Hub sensor entities."""
    client = hass.data[DOMAIN]["client"]

    switches = [
        GeniusBinarySensor(d) for d in client.device_objs if d.type[:21] in GH_IS_SWITCH
    ]

    async_add_entities(switches)


class GeniusBinarySensor(GeniusEntity, BinarySensorDevice):
    """Representation of a Genius Hub binary_sensor."""

    def __init__(self, device) -> None:
        """Initialize the binary sensor."""
        super().__init__()

        self._device = device
        if device.type[:21] == "Dual Channel Receiver":
            self._name = f"Dual Channel Receiver {device.id}"
        else:
            self._name = f"{device.type} {device.id}"

    @property
    def is_on(self) -> bool:
        """Return the status of the sensor."""
        return self._device.data["state"]["outputOnOff"]

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the device state attributes."""
        attrs = {}
        attrs["assigned_zone"] = self._device.data["assignedZones"][0]["name"]

        # pylint: disable=protected-access
        last_comms = self._device._raw["childValues"]["lastComms"]["val"]
        if last_comms != 0:
            attrs["last_comms"] = utc_from_timestamp(last_comms).isoformat()

        return {**attrs}
