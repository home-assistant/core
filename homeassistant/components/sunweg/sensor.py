"""Read status of SunWEG inverters."""

from __future__ import annotations

import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DeviceType
from .coordinator import SunWEGDataUpdateCoordinator
from .sensor_types.inverter import INVERTER_SENSOR_TYPES
from .sensor_types.phase import PHASE_SENSOR_TYPES
from .sensor_types.sensor_entity_description import SunWEGSensorEntityDescription
from .sensor_types.string import STRING_SENSOR_TYPES
from .sensor_types.total import TOTAL_SENSOR_TYPES


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SunWEG sensor."""
    coordinator: SunWEGDataUpdateCoordinator = config_entry.runtime_data

    entities = [
        SunWEGSensor(
            name=f"{coordinator.plant_name} Total",
            unique_id=f"{coordinator.plant_id}-{description.key}",
            coordinator=coordinator,
            description=description,
            device_type=DeviceType.TOTAL,
        )
        for description in TOTAL_SENSOR_TYPES
    ]

    # Add sensors for each device in the specified plant.
    entities.extend(
        [
            SunWEGSensor(
                name=f"{device.name}",
                unique_id=f"{device.sn}-{description.key}",
                coordinator=coordinator,
                description=description,
                device_type=DeviceType.INVERTER,
                inverter_id=device.id,
            )
            for device in coordinator.data.inverters
            for description in INVERTER_SENSOR_TYPES
        ]
    )

    entities.extend(
        [
            SunWEGSensor(
                name=f"{device.name} {phase.name}",
                unique_id=f"{device.sn}-{phase.name}-{description.key}",
                coordinator=coordinator,
                description=description,
                inverter_id=device.id,
                device_type=DeviceType.PHASE,
                deep_name=phase.name,
            )
            for device in coordinator.data.inverters
            for phase in device.phases
            for description in PHASE_SENSOR_TYPES
        ]
    )

    entities.extend(
        [
            SunWEGSensor(
                name=f"{device.name} {string.name}",
                unique_id=f"{device.sn}-{string.name}-{description.key}",
                coordinator=coordinator,
                description=description,
                inverter_id=device.id,
                device_type=DeviceType.STRING,
                deep_name=string.name,
            )
            for device in coordinator.data.inverters
            for mppt in device.mppts
            for string in mppt.strings
            for description in STRING_SENSOR_TYPES
        ]
    )

    async_add_entities(entities, True)


class SunWEGSensor(CoordinatorEntity[SunWEGDataUpdateCoordinator], SensorEntity):
    """Representation of a SunWEG Sensor."""

    entity_description: SunWEGSensorEntityDescription

    def __init__(
        self,
        name: str,
        unique_id: str,
        coordinator: SunWEGDataUpdateCoordinator,
        description: SunWEGSensorEntityDescription,
        device_type: DeviceType,
        inverter_id: int = 0,
        deep_name: str | None = None,
    ) -> None:
        """Initialize a sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.device_type = device_type
        self.inverter_id = inverter_id
        self.deep_name = deep_name

        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = unique_id
        self._attr_icon = (
            description.icon if description.icon is not None else "mdi:solar-power"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.plant_id))},
            manufacturer="SunWEG",
            name=coordinator.plant_name,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        previous_value = self.native_value
        value: StateType | datetime.datetime = self.coordinator.get_api_value(
            self.entity_description.api_variable_key,
            self.device_type,
            self.inverter_id,
            self.deep_name,
        )
        previous_unit_of_measurement: str | None = self.native_unit_of_measurement
        unit_of_measurement: str | None = (
            str(
                self.coordinator.get_api_value(
                    self.entity_description.api_variable_unit,
                    self.device_type,
                    self.inverter_id,
                    self.deep_name,
                )
            )
            if self.entity_description.api_variable_unit is not None
            else self.native_unit_of_measurement
        )

        # Never resets validation
        if (
            self.entity_description.never_resets
            and isinstance(previous_value, float)
            and (value is None or value == 0)
        ):
            value = previous_value
            unit_of_measurement = previous_unit_of_measurement

        self._attr_native_value = value
        self._attr_native_unit_of_measurement = unit_of_measurement
        super()._handle_coordinator_update()
