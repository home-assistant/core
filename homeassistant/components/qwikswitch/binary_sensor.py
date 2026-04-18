"""Support for Qwikswitch Binary Sensors."""

from __future__ import annotations

import logging
from typing import Any

from pyqwikswitch.qwikswitch import SENSORS

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DATA_QUIKSWITCH, DOMAIN
from .entity import QSEntity

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

    qsusb = hass.data[DATA_QUIKSWITCH]
    _LOGGER.debug("Setup qwikswitch.binary_sensor %s, %s", qsusb, discovery_info)
    devs = [QSBinarySensor(sensor) for sensor in discovery_info[DOMAIN]]
    add_entities(devs)


class QSBinarySensor(QSEntity, BinarySensorEntity):
    """Sensor based on a Qwikswitch relay/dimmer module."""

    def __init__(self, sensor: dict[str, Any]) -> None:
        """Initialize the sensor."""

        super().__init__(sensor["id"], sensor["name"])
        self.channel = sensor["channel"]
        sensor_type = sensor["type"]

        self._decode, _ = SENSORS[sensor_type]
        self._invert = not sensor.get("invert", False)
        self._attr_is_on = not self._invert
        self._attr_device_class = sensor.get("class", BinarySensorDeviceClass.DOOR)
        self._attr_unique_id = f"qs{self.qsid}:{self.channel}"

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
            self._attr_is_on = bool(val) == self._invert
            self.async_write_ha_state()
