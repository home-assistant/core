"""Support for Minut Point sensors."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.sensor import (
    DOMAIN,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    PRESSURE_HPA,
    SOUND_PRESSURE_WEIGHTED_DBA,
    TEMP_CELSIUS,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.dt import parse_datetime

from . import MinutPointEntity
from .const import DOMAIN as POINT_DOMAIN, POINT_DISCOVERY_NEW

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_SOUND = "sound_level"


@dataclass
class MinutPointRequiredKeysMixin:
    """Mixin for required keys."""

    precision: int


@dataclass
class MinutPointSensorEntityDescription(
    SensorEntityDescription, MinutPointRequiredKeysMixin
):
    """Describes MinutPoint sensor entity."""


SENSOR_TYPES: tuple[MinutPointSensorEntityDescription, ...] = (
    MinutPointSensorEntityDescription(
        key="temperature",
        precision=1,
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    MinutPointSensorEntityDescription(
        key="pressure",
        precision=0,
        device_class=DEVICE_CLASS_PRESSURE,
        native_unit_of_measurement=PRESSURE_HPA,
    ),
    MinutPointSensorEntityDescription(
        key="humidity",
        precision=1,
        device_class=DEVICE_CLASS_HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    MinutPointSensorEntityDescription(
        key="sound",
        precision=1,
        device_class=DEVICE_CLASS_SOUND,
        icon="mdi:ear-hearing",
        native_unit_of_measurement=SOUND_PRESSURE_WEIGHTED_DBA,
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a Point's sensors based on a config entry."""

    async def async_discover_sensor(device_id):
        """Discover and add a discovered sensor."""
        client = hass.data[POINT_DOMAIN][config_entry.entry_id]
        async_add_entities(
            [
                MinutPointSensor(client, device_id, description)
                for description in SENSOR_TYPES
            ],
            True,
        )

    async_dispatcher_connect(
        hass, POINT_DISCOVERY_NEW.format(DOMAIN, POINT_DOMAIN), async_discover_sensor
    )


class MinutPointSensor(MinutPointEntity, SensorEntity):
    """The platform class required by Home Assistant."""

    entity_description: MinutPointSensorEntityDescription

    def __init__(
        self, point_client, device_id, description: MinutPointSensorEntityDescription
    ):
        """Initialize the sensor."""
        super().__init__(point_client, device_id, description.device_class)
        self.entity_description = description

    async def _update_callback(self):
        """Update the value of the sensor."""
        _LOGGER.debug("Update sensor value for %s", self)
        if self.is_updated:
            self._value = await self.device.sensor(self.device_class)
            self._updated = parse_datetime(self.device.last_update)
        self.async_write_ha_state()

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.value is None:
            return None
        return round(self.value, self.entity_description.precision)
