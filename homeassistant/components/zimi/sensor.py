"""Platform for sensor integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

# Import the device class from the component that you want to support.
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONTROLLER, DOMAIN
from .controller import ZimiController

SENSOR_KEY_DOOR_TEMP = "door_temperature"
SENSOR_KEY_GARAGE_BATTERY = "garage_battery"
SENSOR_KEY_GARAGE_HUMDITY = "garage_humidity"
SENSOR_KEY_GARAGE_TEMP = "garage_temperature"

GARAGE_SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=SENSOR_KEY_DOOR_TEMP,
        name="Outside temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key=SENSOR_KEY_GARAGE_BATTERY,
        name="Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.BATTERY,
    ),
    SensorEntityDescription(
        key=SENSOR_KEY_GARAGE_TEMP,
        name="Garage temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key=SENSOR_KEY_GARAGE_HUMDITY,
        name="Garage humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zimi Sensor platform."""

    debug = config_entry.data.get("debug", False)

    controller: ZimiController = hass.data[CONTROLLER]

    for device in controller.controller.sensors:
        entities = [
            ZimiSensor(device, description, debug=debug)
            for description in GARAGE_SENSOR_DESCRIPTIONS
        ]

        async_add_entities(entities)


class ZimiSensor(SensorEntity):
    """Representation of a Zimi sensor."""

    def __init__(
        self,
        sensor,
        description: SensorEntityDescription,
        debug: bool = False,
    ) -> None:
        """Initialize an ZimiSensor with specified type."""

        self.logger = logging.getLogger(__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)

        self.entity_description = description
        self._attr_unique_id = sensor.identifier + "." + self.entity_description.key
        self._sensor = sensor
        self._state = None

        self._sensor.subscribe(self)

        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, sensor.identifier + "." + self.entity_description.key)
            },
            name=str(self.entity_description.name),
            suggested_area=self._sensor.room,
        )

        self.update()
        self.logger.debug("__init__(%s) in %s", self.name, self._sensor.room)

    def __del__(self):
        """Cleanup ZimiSensor with removal of notification."""
        self._sensor.unsubscribe(self)

    @property
    def available(self) -> bool:
        """Return True if Home Assistant is able to read the state and control the underlying device."""
        return self._sensor.is_connected

    @property
    def name(self) -> str:
        """Return the display name of this cover."""
        return self._name.strip()

    def notify(self, _observable):
        """Receive notification from sensor device that state has changed."""

        self.logger.debug("notification() for %s received", self.name)
        self.schedule_update_ha_state(force_refresh=True)

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self._state

    def update(self) -> None:
        """Fetch new state data for this sensor."""

        if self.entity_description.key == SENSOR_KEY_DOOR_TEMP:
            self._state = self._sensor.door_temp

        if self.entity_description.key == SENSOR_KEY_GARAGE_BATTERY:
            self._state = self._sensor.battery_level

        if self.entity_description.key == SENSOR_KEY_GARAGE_HUMDITY:
            self._state = self._sensor.garage_humidity

        if self.entity_description.key == SENSOR_KEY_GARAGE_TEMP:
            self._state = self._sensor.garage_temp

        if self._sensor.name != "":
            self._name = self._sensor.name + "-" + self.entity_description.name
        else:
            self._name = self.entity_description.name
