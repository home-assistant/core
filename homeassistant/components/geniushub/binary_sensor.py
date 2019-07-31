"""Support for Genius Hub binary_sensor devices."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.dt import utc_from_timestamp

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

GH_IS_SWITCH = ["Dual Channel Receiver", "Electric Switch", "Smart Plug"]


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Genius Hub sensor entities."""
    client = hass.data[DOMAIN]["client"]

    devices = [d for d in client.hub.device_objs if d.type is not None]
    switches = [
        GeniusBinarySensor(client, d) for d in devices if d.type[:21] in GH_IS_SWITCH
    ]

    async_add_entities(switches)


class GeniusBinarySensor(BinarySensorDevice):
    """Representation of a Genius Hub binary_sensor."""

    def __init__(self, client, device):
        """Initialize the binary sensor."""
        self._client = client
        self._device = device

        if device.type[:21] == "Dual Channel Receiver":
            self._name = "Dual Channel Receiver {}".format(device.id)
        else:
            self._name = "{} {}".format(device.type, device.id)

    async def async_added_to_hass(self):
        """Set up a listener when this entity is added to HA."""
        async_dispatcher_connect(self.hass, DOMAIN, self._refresh)

    @callback
    def _refresh(self):
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """Return False as the geniushub devices should not be polled."""
        return False

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._device.state["outputOnOff"]

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attrs = {}
        attrs["assigned_zone"] = self._device.assignedZones[0]["name"]

        # noqa; pylint: disable=protected-access
        last_comms = self._device._raw_json["childValues"]["lastComms"]["val"]
        if last_comms != 0:
            attrs["last_comms"] = utc_from_timestamp(last_comms).isoformat()

        return {**attrs}
