"""Support for Qwikswitch Binary Sensors."""

from __future__ import annotations

import logging

from pyqwikswitch.qwikswitch import SENSORS

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN as QWIKSWITCH, QSEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    _: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Add binary sensor from the main Qwikswitch component."""
    if discovery_info is None:
        return

    qsusb = hass.data[QWIKSWITCH]
    _LOGGER.debug("Setup qwikswitch.binary_sensor %s, %s", qsusb, discovery_info)
    devs = [QSBinarySensor(sensor) for sensor in discovery_info[QWIKSWITCH]]
    add_entities(devs)


class QSBinarySensor(QSEntity, BinarySensorEntity):
    """Sensor based on a Qwikswitch relay/dimmer module."""

    _val = False

    def __init__(self, sensor):
        """Initialize the sensor."""

        super().__init__(sensor["id"], sensor["name"])
        self.channel = sensor["channel"]
        sensor_type = sensor["type"]

        self._decode, _ = SENSORS[sensor_type]
        self._invert = not sensor.get("invert", False)
        self._class = sensor.get("class", "door")

    @callback
    def update_packet(self, packet):
        """Receive update packet from QSUSB."""
        val = self._decode(packet, channel=self.channel)
        _LOGGER.debug(
            "Update %s (%s:%s) decoded as %s: %s",
            self.entity_id,
            self.qsid,
            self.channel,
            val,
            packet,
        )
        if val is not None:
            self._val = bool(val)
            self.async_write_ha_state()

    @property
    def is_on(self):
        """Check if device is on (non-zero)."""
        return self._val == self._invert

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return f"qs{self.qsid}:{self.channel}"

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._class
