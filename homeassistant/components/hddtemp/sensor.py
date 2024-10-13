"""Support for getting the disk temperature of a host."""

from __future__ import annotations

from datetime import timedelta
import logging
import socket
from telnetlib import Telnet  # pylint: disable=deprecated-module
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import (
    CONF_DISKS,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE = "device"
ATTR_MODEL = "model"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 7634
DEFAULT_NAME = "HD Temperature"
DEFAULT_TIMEOUT = 5

SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DISKS, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the HDDTemp sensor."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    disks = config.get(CONF_DISKS)

    hddtemp = HddTempData(host, port)
    hddtemp.update()

    if not disks:
        disks = [next(iter(hddtemp.data)).split("|")[0]]

    add_entities((HddTempSensor(name, disk, hddtemp) for disk in disks), True)


class HddTempSensor(SensorEntity):
    """Representation of a HDDTemp sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE

    def __init__(self, name, disk, hddtemp):
        """Initialize a HDDTemp sensor."""
        self.hddtemp = hddtemp
        self.disk = disk
        self._attr_name = f"{name} {disk}"
        self._details = None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the sensor."""
        if self._details is not None:
            return {ATTR_DEVICE: self._details[0], ATTR_MODEL: self._details[1]}
        return None

    def update(self) -> None:
        """Get the latest data from HDDTemp daemon and updates the state."""
        self.hddtemp.update()

        if self.hddtemp.data and self.disk in self.hddtemp.data:
            self._details = self.hddtemp.data[self.disk].split("|")
            self._attr_native_value = self._details[2]
            if self._details is not None and self._details[3] == "F":
                self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
            else:
                self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        else:
            self._attr_native_value = None


class HddTempData:
    """Get the latest data from HDDTemp and update the states."""

    def __init__(self, host, port):
        """Initialize the data object."""
        self.host = host
        self.port = port
        self.data = None

    def update(self):
        """Get the latest data from HDDTemp running as daemon."""
        try:
            connection = Telnet(host=self.host, port=self.port, timeout=DEFAULT_TIMEOUT)
            data = (
                connection.read_all()
                .decode("ascii")
                .lstrip("|")
                .rstrip("|")
                .split("||")
            )
            self.data = {data[i].split("|")[0]: data[i] for i in range(0, len(data), 1)}
        except ConnectionRefusedError:
            _LOGGER.error("HDDTemp is not available at %s:%s", self.host, self.port)
            self.data = None
        except socket.gaierror:
            _LOGGER.error("HDDTemp host not found %s:%s", self.host, self.port)
            self.data = None
