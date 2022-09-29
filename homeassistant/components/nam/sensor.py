"""Support for the Nettigo Air Monitor service."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import cast

from homeassistant.components.sensor import (
    DOMAIN as PLATFORM,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    PRESSURE_HPA,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utcnow

from . import NAMDataUpdateCoordinator
from .const import (
    ATTR_BME280_HUMIDITY,
    ATTR_BME280_PRESSURE,
    ATTR_BME280_TEMPERATURE,
    ATTR_BMP180_PRESSURE,
    ATTR_BMP180_TEMPERATURE,
    ATTR_BMP280_PRESSURE,
    ATTR_BMP280_TEMPERATURE,
    ATTR_DHT22_HUMIDITY,
    ATTR_DHT22_TEMPERATURE,
    ATTR_HECA_HUMIDITY,
    ATTR_HECA_TEMPERATURE,
    ATTR_MHZ14A_CARBON_DIOXIDE,
    ATTR_SDS011_CAQI,
    ATTR_SDS011_CAQI_LEVEL,
    ATTR_SDS011_P1,
    ATTR_SDS011_P2,
    ATTR_SHT3X_HUMIDITY,
    ATTR_SHT3X_TEMPERATURE,
    ATTR_SIGNAL_STRENGTH,
    ATTR_SPS30_CAQI,
    ATTR_SPS30_CAQI_LEVEL,
    ATTR_SPS30_P0,
    ATTR_SPS30_P1,
    ATTR_SPS30_P2,
    ATTR_SPS30_P4,
    ATTR_UPTIME,
    DOMAIN,
    MIGRATION_SENSORS,
)

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=ATTR_BME280_HUMIDITY,
        name="BME280 humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_BME280_PRESSURE,
        name="BME280 pressure",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_BME280_TEMPERATURE,
        name="BME280 temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_BMP180_PRESSURE,
        name="BMP180 pressure",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_BMP180_TEMPERATURE,
        name="BMP180 temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_BMP280_PRESSURE,
        name="BMP280 pressure",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_BMP280_TEMPERATURE,
        name="BMP280 temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_HECA_HUMIDITY,
        name="HECA humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_HECA_TEMPERATURE,
        name="HECA temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_MHZ14A_CARBON_DIOXIDE,
        name="MH-Z14A carbon dioxide",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_SDS011_CAQI,
        name="SDS011 CAQI",
        icon="mdi:air-filter",
    ),
    SensorEntityDescription(
        key=ATTR_SDS011_CAQI_LEVEL,
        name="SDS011 CAQI level",
        icon="mdi:air-filter",
        device_class="nam__caqi_level",
    ),
    SensorEntityDescription(
        key=ATTR_SDS011_P1,
        name="SDS011 particulate matter 10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_SDS011_P2,
        name="SDS011 particulate matter 2.5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_SHT3X_HUMIDITY,
        name="SHT3X humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_SHT3X_TEMPERATURE,
        name="SHT3X temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_SPS30_CAQI,
        name="SPS30 CAQI",
        icon="mdi:air-filter",
    ),
    SensorEntityDescription(
        key=ATTR_SPS30_CAQI_LEVEL,
        name="SPS30 CAQI level",
        icon="mdi:air-filter",
        device_class="nam__caqi_level",
    ),
    SensorEntityDescription(
        key=ATTR_SPS30_P0,
        name="SPS30 particulate matter 1.0",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_SPS30_P1,
        name="SPS30 particulate matter 10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_SPS30_P2,
        name="SPS30 particulate matter 2.5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_SPS30_P4,
        name="SPS30 particulate matter 4.0",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        icon="mdi:molecule",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_DHT22_HUMIDITY,
        name="DHT22 humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_DHT22_TEMPERATURE,
        name="DHT22 temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_SIGNAL_STRENGTH,
        name="Signal strength",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=ATTR_UPTIME,
        name="Uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add a Nettigo Air Monitor entities from a config_entry."""
    coordinator: NAMDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Due to the change of the attribute name of two sensors, it is necessary to migrate
    # the unique_ids to the new names.
    ent_reg = entity_registry.async_get(hass)
    for old_sensor, new_sensor in MIGRATION_SENSORS:
        old_unique_id = f"{coordinator.unique_id}-{old_sensor}"
        new_unique_id = f"{coordinator.unique_id}-{new_sensor}"
        if entity_id := ent_reg.async_get_entity_id(PLATFORM, DOMAIN, old_unique_id):
            _LOGGER.debug(
                "Migrating entity %s from old unique ID '%s' to new unique ID '%s'",
                entity_id,
                old_unique_id,
                new_unique_id,
            )
            ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)

    sensors: list[NAMSensor | NAMSensorUptime] = []
    for description in SENSORS:
        if getattr(coordinator.data, description.key) is not None:
            if description.key == ATTR_UPTIME:
                sensors.append(NAMSensorUptime(coordinator, description))
            else:
                sensors.append(NAMSensor(coordinator, description))

    async_add_entities(sensors, False)


class NAMSensor(CoordinatorEntity[NAMDataUpdateCoordinator], SensorEntity):
    """Define an Nettigo Air Monitor sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NAMDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.unique_id}-{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state."""
        return cast(
            StateType, getattr(self.coordinator.data, self.entity_description.key)
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        available = super().available

        # For a short time after booting, the device does not return values for all
        # sensors. For this reason, we mark entities for which data is missing as
        # unavailable.
        return (
            available
            and getattr(self.coordinator.data, self.entity_description.key) is not None
        )


class NAMSensorUptime(NAMSensor):
    """Define an Nettigo Air Monitor uptime sensor."""

    @property
    def native_value(self) -> datetime:
        """Return the state."""
        uptime_sec = getattr(self.coordinator.data, self.entity_description.key)
        return utcnow() - timedelta(seconds=uptime_sec)
