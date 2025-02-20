"""Sensor for PG LAB Electronics."""

from __future__ import annotations

from datetime import datetime, timedelta

from pypglab.const import SENSOR_REBOOT_TIME, SENSOR_TEMPERATURE, SENSOR_VOLTAGE
from pypglab.device import Device as PyPGLabDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import Platform, UnitOfElectricPotential, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import utcnow

from . import PGLABConfigEntry
from .device_sensor import PGLabDeviceSensor
from .entity import PGLabEntity

SENSOR_INFO: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key=SENSOR_TEMPERATURE,
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_VOLTAGE,
        translation_key="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_REBOOT_TIME,
        translation_key="runtime",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:progress-clock",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PGLABConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor for device."""

    @callback
    def async_discover(
        pglab_device: PyPGLabDevice,
        pglab_device_sensor: PGLabDeviceSensor,
    ) -> None:
        """Discover and add a PG LAB Sensor."""
        pglab_discovery = config_entry.runtime_data

        for description in SENSOR_INFO:
            pglab_sensor = PGLabSensor(pglab_device, pglab_device_sensor, description)
            async_add_entities([pglab_sensor])

            # Inform PGLab discovery instance that a new entity is available.
            # This is important to know in case the device needs to be reconfigured
            # and the entity can be potentially destroyed.
            pglab_discovery.add_entity(pglab_sensor, pglab_device.id)

    # Register the callback to create the sensor entity when discovered.
    pglab_discovery = config_entry.runtime_data
    await pglab_discovery.register_platform(hass, Platform.SENSOR, async_discover)


PARALLEL_UPDATES = 0


class PGLabSensor(PGLabEntity, SensorEntity):
    """A PGLab sensor."""

    def __init__(
        self,
        pglab_device: PyPGLabDevice,
        pglab_device_sensor: PGLabDeviceSensor,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the Sensor class."""

        super().__init__(
            device=pglab_device,
            entity=pglab_device_sensor.sensors,
        )

        self._type = description.key
        self._pglab_device_sensor = pglab_device_sensor
        self._attr_unique_id = f"{pglab_device.id}_{description.key}"
        self._state: str | datetime | None = None
        self.entity_description = description

        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            self._state = utcnow()
        else:
            self._state = "0"

    @callback
    def state_updated(self, payload: str) -> None:
        """Handle state updates."""

        # get the sensor value from pglab multi fields sensor
        value = self._pglab_device_sensor.state[self._type]

        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            self._state = utcnow() - timedelta(seconds=value)
        else:
            self._state = value

        super().state_updated(payload)

    @property
    def native_value(self) -> str | datetime | None:
        """Return the state of the entity."""
        return self._state

    async def subscribe_to_update(self):
        """Register the HA sensor to be notify when the sensor status is changed."""
        self._pglab_device_sensor.add_ha_sensor(self)

    async def unsubscribe_to_update(self):
        """Unregister the HA sensor from sensor tatus updates."""
        self._pglab_device_sensor.remove_ha_sensor(self)
