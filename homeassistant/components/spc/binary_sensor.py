"""Support for Vanderbilt (formerly Siemens) SPC alarm systems."""
from pyspcwebgw.const import ZoneInput, ZoneType

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_SMOKE,
    BinarySensorEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DATA_API, SIGNAL_UPDATE_SENSOR


def _get_device_class(zone_type):
    return {
        ZoneType.ALARM: DEVICE_CLASS_MOTION,
        ZoneType.ENTRY_EXIT: DEVICE_CLASS_OPENING,
        ZoneType.FIRE: DEVICE_CLASS_SMOKE,
        ZoneType.TECHNICAL: "power",
    }.get(zone_type)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the SPC binary sensor."""
    if discovery_info is None:
        return
    api = hass.data[DATA_API]
    async_add_entities(
        [
            SpcBinarySensor(zone)
            for zone in api.zones.values()
            if _get_device_class(zone.type)
        ]
    )


class SpcBinarySensor(BinarySensorEntity):
    """Representation of a sensor based on a SPC zone."""

    def __init__(self, zone):
        """Initialize the sensor device."""
        self._zone = zone

    async def async_added_to_hass(self):
        """Call for adding new entities."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE_SENSOR.format(self._zone.id),
                self._update_callback,
            )
        )

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
