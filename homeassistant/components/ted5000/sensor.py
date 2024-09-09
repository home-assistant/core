"""Support gathering ted5000 information."""

from __future__ import annotations

from contextlib import suppress
from datetime import timedelta
import logging

import requests
import voluptuous as vol
import xmltodict

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    UnitOfElectricPotential,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "ted"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)


PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=80): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

SENSORS = [
    SensorEntityDescription(
        key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Ted5000 sensor."""
    host: str = config[CONF_HOST]
    port: int = config[CONF_PORT]
    name: str = config[CONF_NAME]
    url = f"http://{host}:{port}/api/LiveData.xml"

    gateway = Ted5000Gateway(url)

    # Get MUT information to create the sensors.
    gateway.update()

    add_entities(
        Ted5000Sensor(gateway, name, mtu, description)
        for mtu in gateway.data
        for description in SENSORS
    )


class Ted5000Sensor(SensorEntity):
    """Implementation of a Ted5000 sensor."""

    def __init__(
        self,
        gateway: Ted5000Gateway,
        name: str,
        mtu: int,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self._gateway = gateway
        self._attr_name = f"{name} mtu{mtu} {description.key}"
        self._mtu = mtu
        self.entity_description = description
        self.update()

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the resources."""
        if unit := self.entity_description.native_unit_of_measurement:
            with suppress(KeyError):
                return self._gateway.data[self._mtu][unit]
        return None

    def update(self) -> None:
        """Get the latest data from REST API."""
        self._gateway.update()


class Ted5000Gateway:
    """The class for handling the data retrieval."""

    def __init__(self, url: str) -> None:
        """Initialize the data object."""
        self.url = url
        self.data: dict[int, dict[str, int | float]] = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Get the latest data from the Ted5000 XML API."""

        try:
            request = requests.get(self.url, timeout=10)
        except requests.exceptions.RequestException as err:
            _LOGGER.error("No connection to endpoint: %s", err)
        else:
            doc = xmltodict.parse(request.text)
            mtus = int(doc["LiveData"]["System"]["NumberMTU"])

            for mtu in range(1, mtus + 1):
                power = int(doc["LiveData"]["Power"]["MTU%d" % mtu]["PowerNow"])
                voltage = int(doc["LiveData"]["Voltage"]["MTU%d" % mtu]["VoltageNow"])

                self.data[mtu] = {
                    UnitOfPower.WATT: power,
                    UnitOfElectricPotential.VOLT: voltage / 10,
                }
