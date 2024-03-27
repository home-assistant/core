"""Support for Minut Point sensors."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfSoundPressure, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import parse_datetime

from . import MinutPointEntity
from .const import DOMAIN as POINT_DOMAIN, POINT_DISCOVERY_NEW

_LOGGER = logging.getLogger(__name__)


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        suggested_display_precision=1,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="humidity",
        suggested_display_precision=1,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="sound",
        suggested_display_precision=1,
        device_class=SensorDeviceClass.SOUND_PRESSURE,
        native_unit_of_measurement=UnitOfSoundPressure.WEIGHTED_DECIBEL_A,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
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

    def __init__(
        self, point_client, device_id, description: SensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(point_client, device_id, description.device_class)
        self.entity_description = description

    async def _update_callback(self):
        """Update the value of the sensor."""
        _LOGGER.debug("Update sensor value for %s", self)
        if self.is_updated:
            self._attr_native_value = await self.device.sensor(self.device_class)
            self._updated = parse_datetime(self.device.last_update)
        self.async_write_ha_state()
