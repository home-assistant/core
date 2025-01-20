"""Support for Fibaro sensors."""

from __future__ import annotations

from contextlib import suppress

from pyfibaro.fibaro_device import DeviceModel

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    Platform,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import convert

from . import FibaroConfigEntry
from .entity import FibaroEntity

# List of known sensors which represents a fibaro device
MAIN_SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    "com.fibaro.temperatureSensor": SensorEntityDescription(
        key="com.fibaro.temperatureSensor",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "com.fibaro.smokeSensor": SensorEntityDescription(
        key="com.fibaro.smokeSensor",
        name="Smoke",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        icon="mdi:fire",
    ),
    "CO2": SensorEntityDescription(
        key="CO2",
        name="CO2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "com.fibaro.humiditySensor": SensorEntityDescription(
        key="com.fibaro.humiditySensor",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "com.fibaro.lightSensor": SensorEntityDescription(
        key="com.fibaro.lightSensor",
        name="Light",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "com.fibaro.energyMeter": SensorEntityDescription(
        key="com.fibaro.energyMeter",
        name="Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
}

# List of additional sensors which are created based on a property
# The key is the property name
ADDITIONAL_SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="energy",
        name="Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="power",
        name="Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

FIBARO_TO_HASS_UNIT: dict[str, str] = {
    "lux": LIGHT_LUX,
    "C": UnitOfTemperature.CELSIUS,
    "F": UnitOfTemperature.FAHRENHEIT,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FibaroConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fibaro controller devices."""

    controller = entry.runtime_data
    entities: list[SensorEntity] = [
        FibaroSensor(device, MAIN_SENSOR_TYPES.get(device.type))
        for device in controller.fibaro_devices[Platform.SENSOR]
        # Some sensor devices do not have a value but report power or energy.
        # These sensors are added to the sensor list but need to be excluded
        # here as the FibaroSensor expects a value. One example is the
        # Qubino 3 phase power meter.
        if device.value.has_value
    ]

    entities.extend(
        FibaroAdditionalSensor(device, entity_description)
        for platform in (
            Platform.BINARY_SENSOR,
            Platform.CLIMATE,
            Platform.COVER,
            Platform.LIGHT,
            Platform.LOCK,
            Platform.SENSOR,
            Platform.SWITCH,
        )
        for device in controller.fibaro_devices[platform]
        for entity_description in ADDITIONAL_SENSOR_TYPES
        if entity_description.key in device.properties
    )

    async_add_entities(entities, True)


class FibaroSensor(FibaroEntity, SensorEntity):
    """Representation of a Fibaro Sensor."""

    def __init__(
        self,
        fibaro_device: DeviceModel,
        entity_description: SensorEntityDescription | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(fibaro_device)
        if entity_description is not None:
            self.entity_description = entity_description
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)

        # Map unit if it was not defined in the entity description
        # or there is no entity description at all
        with suppress(KeyError, ValueError):
            if not self.native_unit_of_measurement:
                self._attr_native_unit_of_measurement = FIBARO_TO_HASS_UNIT.get(
                    fibaro_device.unit, fibaro_device.unit
                )

    def update(self) -> None:
        """Update the state."""
        super().update()
        with suppress(TypeError):
            self._attr_native_value = self.fibaro_device.value.float_value()


class FibaroAdditionalSensor(FibaroEntity, SensorEntity):
    """Representation of a Fibaro Additional Sensor."""

    def __init__(
        self, fibaro_device: DeviceModel, entity_description: SensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(fibaro_device)
        self.entity_description = entity_description

        # To differentiate additional sensors from main sensors they need
        # to get different names and ids
        self.entity_id = ENTITY_ID_FORMAT.format(
            f"{self.ha_id}_{entity_description.key}"
        )
        self._attr_name = f"{fibaro_device.friendly_name} {entity_description.name}"
        self._attr_unique_id = f"{fibaro_device.unique_id_str}_{entity_description.key}"

    def update(self) -> None:
        """Update the state."""
        super().update()
        with suppress(KeyError, ValueError):
            self._attr_native_value = convert(
                self.fibaro_device.properties[self.entity_description.key],
                float,
            )
