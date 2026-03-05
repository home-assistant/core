"""Sensor platform for Qube Heat Pump."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from python_qube_heatpump.models import QubeState

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower, UnitOfTemperature
from homeassistant.helpers.typing import StateType
from homeassistant.util import slugify

from .entity import QubeEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import QubeConfigEntry
    from .coordinator import QubeCoordinator
    from .hub import QubeHub

_LOGGER = logging.getLogger(__name__)

# Status code to state mapping
STATUS_MAP: dict[int, str] = {
    0: "standby",
    1: "alarm",
    2: "keyboard_off",
    3: "compressor_startup",
    4: "compressor_shutdown",
    5: "cooling",
    6: "heating",
    7: "start_fail",
    8: "heating_dhw",
}


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temp_supply",
        translation_key="temp_supply",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="temp_return",
        translation_key="temp_return",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="temp_source_in",
        translation_key="temp_source_in",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="temp_source_out",
        translation_key="temp_source_out",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="temp_room",
        translation_key="temp_room",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="temp_dhw",
        translation_key="temp_dhw",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="temp_outside",
        translation_key="temp_outside",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="power_thermic",
        translation_key="power_thermic",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="power_electric",
        translation_key="power_electric",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="energy_total_electric",
        translation_key="energy_total_electric",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
    ),
    SensorEntityDescription(
        key="energy_total_thermic",
        translation_key="energy_total_thermic",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
    ),
    SensorEntityDescription(
        key="cop_calc",
        translation_key="cop_calc",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="compressor_speed",
        translation_key="compressor_speed",
        native_unit_of_measurement="rpm",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="flow_rate",
        translation_key="flow_rate",
        native_unit_of_measurement="L/min",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="setpoint_room_heat_day",
        translation_key="setpoint_room_heat_day",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="setpoint_room_heat_night",
        translation_key="setpoint_room_heat_night",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="setpoint_room_cool_day",
        translation_key="setpoint_room_cool_day",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="setpoint_room_cool_night",
        translation_key="setpoint_room_cool_night",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="setpoint_dhw",
        translation_key="setpoint_dhw",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QubeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Qube sensors."""
    data = entry.runtime_data
    hub = data.hub
    coordinator = data.coordinator
    version = data.version or "unknown"
    device_name = data.device_name

    entities: list[SensorEntity] = [
        QubeSensor(
            coordinator,
            hub,
            entry,
            version,
            device_name,
            description,
        )
        for description in SENSOR_TYPES
    ]

    # Status sensor (computed with enum device class)
    entities.append(
        QubeStatusSensor(
            coordinator,
            hub,
            entry,
            version,
            device_name,
        )
    )

    async_add_entities(entities)


class QubeSensor(QubeEntity, SensorEntity):
    """Qube generic sensor."""

    entity_description: SensorEntityDescription
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: QubeCoordinator,
        hub: QubeHub,
        entry: QubeConfigEntry,
        version: str,
        device_name: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, hub, version, device_name)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}-{description.key}"
        # Use key (vendor_id equivalent) for stable, predictable entity IDs
        label = slugify(device_name) or "qube"
        self.entity_id = f"sensor.{label}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return native value."""
        data: QubeState = self.coordinator.data
        if not data:
            return None
        return getattr(data, self.entity_description.key, None)


class QubeStatusSensor(QubeEntity, SensorEntity):
    """Heat pump status sensor with enum device class."""

    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_translation_key = "status_heatpump"
    _attr_options = [
        "standby",
        "alarm",
        "keyboard_off",
        "compressor_startup",
        "compressor_shutdown",
        "cooling",
        "heating",
        "start_fail",
        "heating_dhw",
    ]

    def __init__(
        self,
        coordinator: QubeCoordinator,
        hub: QubeHub,
        entry: QubeConfigEntry,
        version: str,
        device_name: str,
    ) -> None:
        """Initialize status sensor."""
        super().__init__(coordinator, hub, version, device_name)
        self._attr_unique_id = f"{entry.unique_id}-status_heatpump"
        # Use translation_key for stable, predictable entity IDs
        label = slugify(device_name) or "qube"
        self.entity_id = f"sensor.{label}_status_heatpump"

    @property
    def native_value(self) -> str | None:
        """Return the status as a string for enum translation."""
        data: QubeState = self.coordinator.data
        if not data:
            return None

        code = data.status_code
        if code is None:
            return None
        return STATUS_MAP.get(code)
