"""Sensor platform for the WattWächter Plus integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DIAGNOSTIC_SENSORS,
    KNOWN_OBIS_CODES,
    DiagnosticSensorDescription,
    ObisSensorDescription,
)
from . import WattwaechterConfigEntry
from .coordinator import WattwaechterCoordinator
from .entity import WattwaechterEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

# Map API unit strings to HA unit/device_class/state_class/precision for unknown OBIS codes
UNIT_MAP: dict[str, tuple[str | None, SensorDeviceClass | None, SensorStateClass | None, int | None]] = {
    "kWh": ("kWh", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, 2),
    "Wh": ("Wh", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, 0),
    "W": ("W", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, 0),
    "V": ("V", SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, 1),
    "A": ("A", SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, 2),
    "Hz": ("Hz", SensorDeviceClass.FREQUENCY, SensorStateClass.MEASUREMENT, 2),
    "var": ("var", None, SensorStateClass.MEASUREMENT, 0),
    "VA": ("VA", None, SensorStateClass.MEASUREMENT, 0),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WattwaechterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WattWächter sensors from a config entry."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []

    # Dynamic OBIS sensors from meter data
    if coordinator.data.meter:
        for obis_code, obis_value in coordinator.data.meter.values.items():
            if obis_code in KNOWN_OBIS_CODES:
                # Known OBIS code with predefined metadata
                entities.append(
                    WattwaechterObisSensor(
                        coordinator=coordinator,
                        description=KNOWN_OBIS_CODES[obis_code],
                        obis_code=obis_code,
                    )
                )
            else:
                # Unknown OBIS code - create generic sensor from API data
                api_unit = obis_value.unit
                value = obis_value.value
                is_numeric = isinstance(value, (int, float))

                if api_unit and api_unit in UNIT_MAP:
                    unit, device_class, state_class, precision = UNIT_MAP[api_unit]
                elif is_numeric:
                    unit = api_unit or None
                    device_class = None
                    state_class = SensorStateClass.MEASUREMENT
                    precision = None
                else:
                    # String values (e.g. meter number, manufacturer code)
                    unit = None
                    device_class = None
                    state_class = None
                    precision = None

                description = ObisSensorDescription(
                    key=obis_code,
                    name=f"OBIS {obis_code}",
                    native_unit_of_measurement=unit,
                    device_class=device_class,
                    state_class=state_class,
                    suggested_display_precision=precision,
                )
                entities.append(
                    WattwaechterObisSensor(
                        coordinator=coordinator,
                        description=description,
                        obis_code=obis_code,
                    )
                )

    # Diagnostic sensors from system info
    if coordinator.data.system:
        for diag_description in DIAGNOSTIC_SENSORS:
            entities.append(
                WattwaechterDiagnosticSensor(
                    coordinator=coordinator,
                    description=diag_description,
                )
            )

    async_add_entities(entities)


class WattwaechterObisSensor(WattwaechterEntity, SensorEntity):
    """Sensor for OBIS meter values."""

    entity_description: ObisSensorDescription

    def __init__(
        self,
        coordinator: WattwaechterCoordinator,
        description: ObisSensorDescription,
        obis_code: str,
    ) -> None:
        """Initialize the OBIS sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._obis_code = obis_code
        self._attr_unique_id = f"{coordinator.device_id}_{obis_code}"

    @property
    def native_value(self) -> float | str | None:
        """Return the current sensor value."""
        if self.coordinator.data.meter is None:
            return None
        obis = self.coordinator.data.meter.values.get(self._obis_code)
        if obis is None:
            return None
        return obis.value


class WattwaechterDiagnosticSensor(WattwaechterEntity, SensorEntity):
    """Sensor for diagnostic system information."""

    entity_description: DiagnosticSensorDescription

    def __init__(
        self,
        coordinator: WattwaechterCoordinator,
        description: DiagnosticSensorDescription,
    ) -> None:
        """Initialize the diagnostic sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def native_value(self) -> str | float | None:
        """Return the current sensor value."""
        system = self.coordinator.data.system
        if not system:
            return None
        return system.get_value(
            self.entity_description.system_section,
            self.entity_description.system_key,
        )
