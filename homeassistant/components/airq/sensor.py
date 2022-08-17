"""Definition of air-Q sensor platform.

This platform initialisation follows immediately after (or as the last part of) the
integration setup, defined in __init__.py.
"""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    PRESSURE_HPA,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AirQCoordinator
from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

# Keys must match those in the data dictionary
SENSOR_TYPES: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="co",
        name="CO",
        device_class=SensorDeviceClass.CO,
        native_unit_of_measurement=CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="co2",
        name="CO2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="no2",
        name="NO2",
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="o3",
        name="Ozone",
        device_class=SensorDeviceClass.OZONE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # The definition in SensorDeviceClass.PM1 says <= 0.1µm, not 1µm.
    # Its documentation, however, says < 1µm
    SensorEntityDescription(
        key="pm1",
        name="PM1",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm2_5",
        name="PM2.5",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm10",
        name="PM10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pressure",
        name="Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="so2",
        name="SO2",
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tvoc",
        name="VOC",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities based on a config entry."""

    coordinator = hass.data[DOMAIN][config.entry_id]
    available_keys = list(coordinator.data.keys())

    # Add sensors under warmup
    status = coordinator.data["Status"]
    if isinstance(status, dict):
        warming_up_sensors = [
            k for k, v in status.items() if "sensor still in warm up phase" in v
        ]
        available_keys.extend(warming_up_sensors)
        _LOGGER.debug(
            "Following %d sensors are warming up: %s",
            len(warming_up_sensors),
            ", ".join(warming_up_sensors),
        )

    # Filter out non-sensor keys and build a list of SensorEntityDescription objects
    available_sensors = [
        description for description in SENSOR_TYPES if description.key in available_keys
    ]
    _LOGGER.debug(
        "Identified %d  available sensors: %s",
        len(available_sensors),
        ", ".join([sensor.key for sensor in available_sensors]),
    )

    entities = [
        AirQSensor(coordinator, description) for description in available_sensors
    ]
    async_add_entities(entities)


class AirQSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AirQCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a single sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_device_info = DeviceInfo(
            # the name (e.g. ABCDE) will be prepended to description.name: 'ABCDE NO2'
            name=coordinator.config["name"],
            model=coordinator.config["model"],
            sw_version=coordinator.config["sw_version"],
            hw_version=coordinator.config["hw_version"],
            identifiers={(DOMAIN, coordinator.config["id"])},
            manufacturer=MANUFACTURER,
            suggested_area=coordinator.config["room_type"],
        )
        self._attr_name = description.name
        self._attr_unique_id = f"{coordinator.config['id']}_{description.key}"

    @property
    def native_value(self) -> float | int | None:
        """Return the value reported by the sensor."""
        # airthings has a neat way of doing it when the data returned by the API
        # are a dictionary with keys for each device, and values being dictionaries
        # of sensor values. Under this condition, the call should be:
        # return self.coordinator.data[self._id].sensors[self.entity_description.key]
        # In our case now, only one device is allowed and self.coordinator.data
        # contains the regular dict retrieved from a single device

        # .get(key, None) over [key] to guard against the keys of the warming up
        # sensors not being present in the returned dictionary
        return self.coordinator.data.get(self.entity_description.key, None)
