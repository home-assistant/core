"""Support for Vanderbilt (formerly Siemens) SPC alarm systems."""
import logging

from pyspcwebgw.const import ZoneInput, ZoneType

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_SMOKE,
    DEVICE_CLASS_POWER,
    BinarySensorEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DATA_KEY, SIGNAL_UPDATE_SENSOR, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _get_device_class(zone_type):
    return {
        ZoneType.ALARM: DEVICE_CLASS_MOTION,
        ZoneType.ENTRY_EXIT: DEVICE_CLASS_OPENING,
        ZoneType.FIRE: DEVICE_CLASS_SMOKE,
        ZoneType.TECHNICAL: DEVICE_CLASS_POWER,
    }.get(zone_type)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the SPC binary sensor."""
    client = hass.data[DATA_KEY][entry.entry_id]
    async_add_entities(
        [
            SpcBinarySensor(zone, client)
            for zone in client.zones.values()
            if _get_device_class(zone.type)
        ]
    )


class SpcBinarySensor(BinarySensorEntity):
    """Representation of a sensor based on a SPC zone."""

    def __init__(self, zone, client):
        """Initialize the sensor device."""
        self._zone = zone
        self._client = client

    async def async_added_to_hass(self):
        """Call for adding new entities."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE_SENSOR.format(self._zone.id),
                self._update_callback,
            )
        )

    @property
    def unique_id(self) -> str:
        """Get the unique identifier of the device."""
        serial = self._client.info["sn"]
        return f"{serial}-{self._zone.area.id}-{self._zone.id}"

    @property
    def device_info(self):
        """Provide device info."""
        serial = self._client.info["sn"]
        owner_device_id = f"{serial}-{self._zone.area.id}"

        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self._zone.name,
            "model": "SPC alarm zone",
            "via_device": (DOMAIN, owner_device_id),
        }

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    @property
    def name(self):
        """Return the name of the device."""
        return self._zone.name

    @property
    def is_on(self):
        """Whether the device is switched on."""
        return self._zone.input == ZoneInput.OPEN

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_class(self):
        """Return the device class."""
        return _get_device_class(self._zone.type)
