"""Support for Pure Energie sensors."""
from __future__ import annotations

from typing import Literal

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, ENERGY_KILO_WATT_HOUR, POWER_WATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PureEnergieDataUpdateCoordinator
from .const import DOMAIN, SERVICE_SMARTMETER, SERVICES

SENSORS: dict[Literal["smartmeter"], tuple[SensorEntityDescription, ...]] = {
    SERVICE_SMARTMETER: (
        SensorEntityDescription(
            key="power_flow",
            name="Power Flow",
            native_unit_of_measurement=POWER_WATT,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SensorEntityDescription(
            key="energy_consumption_total",
            name="Energy Consumption",
            native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        SensorEntityDescription(
            key="energy_production_total",
            name="Energy Production",
            native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Pure Energie Sensors based on a config entry."""
    async_add_entities(
        PureEnergieSensorEntity(
            coordinator=hass.data[DOMAIN][entry.entry_id],
            description=description,
            service_key=service_key,
            name=entry.title,
            service=SERVICES[service_key],
        )
        for service_key, service_sensors in SENSORS.items()
        for description in service_sensors
    )


class PureEnergieSensorEntity(CoordinatorEntity, SensorEntity):
    """Defines an Pure Energie sensor."""

    coordinator: PureEnergieDataUpdateCoordinator

    def __init__(
        self,
        *,
        coordinator: PureEnergieDataUpdateCoordinator,
        description: SensorEntityDescription,
        service_key: Literal["smartmeter"],
        name: str,
        service: str,
    ) -> None:
        """Initialize Pure Energie sensor."""
        super().__init__(coordinator=coordinator)
        self._service_key = service_key

        self.entity_id = f"{SENSOR_DOMAIN}.{name}_{description.key}"
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{service_key}_{description.key}"
        )

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (DOMAIN, f"{coordinator.config_entry.entry_id}_{service_key}")
            },
            configuration_url=f"http://{coordinator.config_entry.data[CONF_HOST]}",
            sw_version=coordinator.data["device"].firmware,
            manufacturer=coordinator.data["device"].manufacturer,
            model=coordinator.data["device"].model,
            name=service,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        value = getattr(
            self.coordinator.data[self._service_key], self.entity_description.key
        )
        return value
