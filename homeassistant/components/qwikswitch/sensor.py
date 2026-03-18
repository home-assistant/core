"""Support for Qwikswitch Sensors."""

from __future__ import annotations

import logging
from typing import Any

from pyqwikswitch.qwikswitch import SENSORS

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN
from .entity import QSEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    _: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Add sensor from the main Qwikswitch component."""
    if discovery_info is None:
        return

    qsusb = hass.data[DOMAIN]
    _LOGGER.debug("Setup qwikswitch.sensor %s, %s", qsusb, discovery_info)
    devs = [QSSensor(sensor) for sensor in discovery_info[DOMAIN]]
    add_entities(devs)


class QSSensor(QSEntity, SensorEntity):
    """Sensor based on a Qwikswitch relay/dimmer module."""

    _val: Any | None = None

    def __init__(self, sensor):
        """Initialize the sensor."""

        super().__init__(sensor["id"], sensor["name"])
        self.channel = sensor["channel"]
        sensor_type = sensor["type"]

        self._decode, self.unit = SENSORS[sensor_type]
        # this cannot happen because it only happens in bool and this should be redirected to binary_sensor
        assert not isinstance(self.unit, type), (
            f"boolean sensor id={sensor['id']} name={sensor['name']}"
        )

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
            self._val = val
            self.async_write_ha_state()

    @property
    def native_value(self):
        """Return the value of the sensor."""
        return None if self._val is None else str(self._val)

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return f"qs{self.qsid}:{self.channel}"

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self.unit
