"""Support for mill wifi-enabled home heaters."""

from __future__ import annotations

import mill

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_IP_ADDRESS,
    CONF_USERNAME,
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BATTERY,
    CLOUD,
    CONNECTION_TYPE,
    CONSUMPTION_TODAY,
    CONSUMPTION_YEAR,
    DOMAIN,
    ECO2,
    HUMIDITY,
    LOCAL,
    MANUFACTURER,
    TEMPERATURE,
    TVOC,
)
from .coordinator import MillDataUpdateCoordinator
from .entity import MillBaseEntity

HEATER_SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=CONSUMPTION_YEAR,
        translation_key="year_consumption",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=CONSUMPTION_TODAY,
        translation_key="day_consumption",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="current_power",
        translation_key="current_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="control_signal",
        translation_key="control_signal",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=BATTERY,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=ECO2,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        translation_key="estimated_co2",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=TVOC,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        translation_key="tvoc",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

LOCAL_SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="control_signal",
        translation_key="control_signal",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="current_power",
        translation_key="current_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="raw_ambient_temperature",
        translation_key="uncalibrated_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
)

SOCKET_SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    *HEATER_SENSOR_TYPES,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Mill sensor."""
    if entry.data.get(CONNECTION_TYPE) == LOCAL:
        mill_data_coordinator = hass.data[DOMAIN][LOCAL][entry.data[CONF_IP_ADDRESS]]

        async_add_entities(
            LocalMillSensor(
                mill_data_coordinator,
                entity_description,
            )
            for entity_description in LOCAL_SENSOR_TYPES
        )
        return

    mill_data_coordinator = hass.data[DOMAIN][CLOUD][entry.data[CONF_USERNAME]]

    entities = [
        MillSensor(
            mill_data_coordinator,
            entity_description,
            mill_device,
        )
        for mill_device in mill_data_coordinator.data.values()
        for entity_description in (
            SOCKET_SENSOR_TYPES
            if isinstance(mill_device, mill.Socket)
            else HEATER_SENSOR_TYPES
            if isinstance(mill_device, mill.Heater)
            else SENSOR_TYPES
        )
    ]

    async_add_entities(entities)


class MillSensor(MillBaseEntity, SensorEntity):
    """Representation of a Mill Sensor device."""

    def __init__(
        self,
        coordinator: MillDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
        mill_device: mill.Socket | mill.Heater,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, mill_device)
        self.entity_description = entity_description
        self._attr_unique_id = f"{mill_device.device_id}_{entity_description.key}"

    @callback
    def _update_attr(self, device):
        self._available = device.available
        self._attr_native_value = getattr(device, self.entity_description.key)


class LocalMillSensor(CoordinatorEntity[MillDataUpdateCoordinator], SensorEntity):
    """Representation of a Mill Sensor device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MillDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        if mac := coordinator.mill_data_connection.mac_address:
            self._attr_unique_id = f"{mac}_{entity_description.key}"
            self._attr_device_info = DeviceInfo(
                connections={(CONNECTION_NETWORK_MAC, mac)},
                configuration_url=self.coordinator.mill_data_connection.url,
                manufacturer=MANUFACTURER,
                model="Generation 3",
                name=coordinator.mill_data_connection.name,
                sw_version=coordinator.mill_data_connection.version,
            )

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        return self.coordinator.data[self.entity_description.key]
