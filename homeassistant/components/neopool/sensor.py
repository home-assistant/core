"""Sensor platform for the NeoPool integration."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
import logging
import math
from typing import Any

from neopool_modbus.capabilities import has_filtvalve, is_ionization_present
from neopool_modbus.decoders import (
    decode_hidro_polarity,
    decode_ion_polarity,
    decode_ph_pump_status,
    get_filtration_pump_type,
    is_hydrolysis_in_percent,
)

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import NeoPoolConfigEntry
from .const import CONF_FILTRATION_PUMP_POWER
from .coordinator import NeoPoolCoordinator
from .entity import NeoPoolEntity
from .helpers import calculate_next_interval_time

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

_FILTRATION_MODE_OPTIONS: tuple[str, ...] = (
    "manual",
    "auto",
    "heating",
    "smart",
    "intelligent",
    "backwash",
)
_FILTRATION_SPEED_OPTIONS: tuple[str, ...] = ("off", "low", "mid", "high")

PH_STATUS_ALARM_MAP = {
    0: "ok",
    1: "ph_high",
    2: "ph_low",
    3: "pump_stopped",
    4: "ph_over",
    5: "ph_under",
    6: "tank_level",
}

type SupportedFn = Callable[[dict[str, Any], Mapping[str, Any]], bool]


@dataclass(frozen=True, kw_only=True)
class NeoPoolSensorEntityDescription(SensorEntityDescription):
    """Describes a NeoPool sensor entity."""

    supported_fn: SupportedFn | None = None


SENSOR_DESCRIPTIONS: dict[str, NeoPoolSensorEntityDescription] = {
    "MBF_ION_CURRENT": NeoPoolSensorEntityDescription(
        key="MBF_ION_CURRENT",
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        supported_fn=lambda data, opts: is_ionization_present(data),
    ),
    "MBF_HIDRO_CURRENT": NeoPoolSensorEntityDescription(
        key="MBF_HIDRO_CURRENT",
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        supported_fn=lambda data, opts: bool(data.get("Hydrolysis module detected")),
    ),
    "MBF_MEASURE_PH": NeoPoolSensorEntityDescription(
        key="MBF_MEASURE_PH",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        supported_fn=lambda data, opts: (
            data.get("pH measurement module detected") is True
        ),
    ),
    "MBF_MEASURE_RX": NeoPoolSensorEntityDescription(
        key="MBF_MEASURE_RX",
        native_unit_of_measurement="mV",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        supported_fn=lambda data, opts: (
            data.get("Redox measurement module detected") is True
        ),
    ),
    "MBF_MEASURE_CL": NeoPoolSensorEntityDescription(
        key="MBF_MEASURE_CL",
        native_unit_of_measurement="ppm",
        state_class=SensorStateClass.MEASUREMENT,
        supported_fn=lambda data, opts: (
            data.get("Chlorine measurement module detected") is True
        ),
    ),
    "MBF_MEASURE_CONDUCTIVITY": NeoPoolSensorEntityDescription(
        key="MBF_MEASURE_CONDUCTIVITY",
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        supported_fn=lambda data, opts: (
            data.get("Conductivity measurement module detected") is True
        ),
    ),
    "MBF_MEASURE_TEMPERATURE": NeoPoolSensorEntityDescription(
        key="MBF_MEASURE_TEMPERATURE",
        native_unit_of_measurement="°C",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        supported_fn=lambda data, opts: bool(data.get("MBF_PAR_TEMPERATURE_ACTIVE")),
    ),
    "MBF_HIDRO_VOLTAGE": NeoPoolSensorEntityDescription(
        key="MBF_HIDRO_VOLTAGE",
        native_unit_of_measurement="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        supported_fn=lambda data, opts: bool(data.get("Hydrolysis module detected")),
    ),
    "MBF_PAR_FILT_MODE": NeoPoolSensorEntityDescription(
        key="MBF_PAR_FILT_MODE",
        device_class=SensorDeviceClass.ENUM,
    ),
    "MBF_PH_STATUS_ALARM": NeoPoolSensorEntityDescription(
        key="MBF_PH_STATUS_ALARM",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=lambda data, opts: (
            data.get("pH measurement module detected") is True
        ),
    ),
    "HIDRO_POLARITY": NeoPoolSensorEntityDescription(
        key="HIDRO_POLARITY",
        device_class=SensorDeviceClass.ENUM,
        supported_fn=lambda data, opts: bool(data.get("Hydrolysis module detected")),
    ),
    "ION_POLARITY": NeoPoolSensorEntityDescription(
        key="ION_POLARITY",
        device_class=SensorDeviceClass.ENUM,
        supported_fn=lambda data, opts: is_ionization_present(data),
    ),
    "PH_PUMP_STATUS": NeoPoolSensorEntityDescription(
        key="PH_PUMP_STATUS",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=lambda data, opts: (
            data.get("pH measurement module detected") is True
        ),
    ),
    "FILTRATION_SPEED": NeoPoolSensorEntityDescription(
        key="FILTRATION_SPEED",
        device_class=SensorDeviceClass.ENUM,
        supported_fn=lambda data, opts: bool(
            get_filtration_pump_type(data.get("MBF_PAR_FILTRATION_CONF", 0))
        ),
    ),
    "MBF_PAR_INTELLIGENT_INTERVALS": NeoPoolSensorEntityDescription(
        key="MBF_PAR_INTELLIGENT_INTERVALS",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=lambda data, opts: (
            bool(data.get("MBF_PAR_HEATING_GPIO"))
            and bool(data.get("MBF_PAR_TEMPERATURE_ACTIVE"))
        ),
    ),
    "MBF_PAR_INTELLIGENT_TT_NEXT_INTERVAL": NeoPoolSensorEntityDescription(
        key="MBF_PAR_INTELLIGENT_TT_NEXT_INTERVAL",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=lambda data, opts: (
            bool(data.get("MBF_PAR_HEATING_GPIO"))
            and bool(data.get("MBF_PAR_TEMPERATURE_ACTIVE"))
        ),
    ),
    "MBF_PAR_FILTVALVE_REMAINING": NeoPoolSensorEntityDescription(
        key="MBF_PAR_FILTVALVE_REMAINING",
        native_unit_of_measurement="s",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        supported_fn=lambda data, opts: has_filtvalve(data),
    ),
    "FILTRATION_REMAINING": NeoPoolSensorEntityDescription(
        key="FILTRATION_REMAINING",
        native_unit_of_measurement="s",
        device_class=SensorDeviceClass.DURATION,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    "CELL_RUNTIME_TOTAL": NeoPoolSensorEntityDescription(
        key="CELL_RUNTIME_TOTAL",
        native_unit_of_measurement="s",
        suggested_unit_of_measurement="h",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=lambda data, opts: bool(data.get("Hydrolysis module detected")),
    ),
    "CELL_RUNTIME_PART": NeoPoolSensorEntityDescription(
        key="CELL_RUNTIME_PART",
        native_unit_of_measurement="s",
        suggested_unit_of_measurement="h",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=lambda data, opts: bool(data.get("Hydrolysis module detected")),
    ),
    "CELL_RUNTIME_POLA": NeoPoolSensorEntityDescription(
        key="CELL_RUNTIME_POLA",
        native_unit_of_measurement="s",
        suggested_unit_of_measurement="h",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=lambda data, opts: bool(data.get("Hydrolysis module detected")),
    ),
    "CELL_RUNTIME_POLB": NeoPoolSensorEntityDescription(
        key="CELL_RUNTIME_POLB",
        native_unit_of_measurement="s",
        suggested_unit_of_measurement="h",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=lambda data, opts: bool(data.get("Hydrolysis module detected")),
    ),
    "CELL_RUNTIME_POL_CHANGES": NeoPoolSensorEntityDescription(
        key="CELL_RUNTIME_POL_CHANGES",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        supported_fn=lambda data, opts: bool(data.get("Hydrolysis module detected")),
    ),
    CONF_FILTRATION_PUMP_POWER: NeoPoolSensorEntityDescription(
        key=CONF_FILTRATION_PUMP_POWER,
        translation_key=CONF_FILTRATION_PUMP_POWER,
        native_unit_of_measurement="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        supported_fn=lambda data, opts: (
            int((opts or {}).get(CONF_FILTRATION_PUMP_POWER, 0) or 0) > 0
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NeoPool sensors from a config entry."""
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = [
        NeoPoolSensor(coordinator, entry.entry_id, key, desc)
        for key, desc in SENSOR_DESCRIPTIONS.items()
        if desc.supported_fn is None
        or desc.supported_fn(coordinator.data, entry.options)
    ]

    pump_power = int(entry.options.get(CONF_FILTRATION_PUMP_POWER, 0) or 0)
    if pump_power > 0:
        entities.append(
            NeoPoolFiltrationEnergySensor(coordinator, entry.entry_id, pump_power)
        )

    async_add_entities(entities)


class NeoPoolSensor(NeoPoolEntity, SensorEntity):
    """Representation of a NeoPool sensor."""

    entity_description: NeoPoolSensorEntityDescription

    def __init__(
        self,
        coordinator: NeoPoolCoordinator,
        entry_id: str,
        key: str,
        description: NeoPoolSensorEntityDescription,
    ) -> None:
        """Initialize the NeoPool sensor entity."""
        super().__init__(coordinator, entry_id)
        self.entity_description = description
        self._key = key
        device_id = self.coordinator.entry.unique_id or self._entry_id
        self._attr_unique_id = f"{device_id}_{key.lower()}"
        self._attr_translation_key = NeoPoolEntity.slugify(key)

    async def async_added_to_hass(self) -> None:
        """Run when the entity is added to hass."""
        _LOGGER.debug(
            "ADDED: entity_id=%s, translation_key=%s, has_entity_name=%s",
            self.entity_id,
            self.translation_key,
            getattr(self, "has_entity_name", None),
        )
        await super().async_added_to_hass()

    @property
    def suggested_display_precision(self) -> int | None:
        """Return the suggested display precision for the sensor value."""
        if self._key == "MBF_HIDRO_CURRENT" and not is_hydrolysis_in_percent(
            self.coordinator.data
        ):
            return 1
        return self.entity_description.suggested_display_precision

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement for the sensor value."""
        if self._key == "MBF_HIDRO_CURRENT" and not is_hydrolysis_in_percent(
            self.coordinator.data
        ):
            return "g/h"
        return self.entity_description.native_unit_of_measurement

    _PRODUCTION_KEYS_REQUIRING_FILTRATION = frozenset(
        {
            "MBF_HIDRO_CURRENT",
            "MBF_HIDRO_VOLTAGE",
            "MBF_ION_CURRENT",
        }
    )

    _MEASURE_KEYS_REQUIRING_FILTRATION = frozenset(
        {
            "MBF_MEASURE_TEMPERATURE",
            "MBF_MEASURE_PH",
            "MBF_MEASURE_RX",
            "MBF_MEASURE_CL",
            "MBF_MEASURE_CONDUCTIVITY",
            "FILTRATION_SPEED",
        }
    )

    def _filtration_gate_blocks(self) -> bool:
        """Return True if the filtration-off gate hides the live reading."""
        return self.coordinator.data.get("Filtration Pump") is False

    def _is_measurement_suppressed(self) -> bool:
        """Return True if a measurement sensor should report None."""
        if self._key not in self._MEASURE_KEYS_REQUIRING_FILTRATION:
            return False
        return self._filtration_gate_blocks()

    def _is_production_suppressed(self) -> bool:
        """Return True if a production sensor should report 0."""
        if self._key not in self._PRODUCTION_KEYS_REQUIRING_FILTRATION:
            return False
        return self._filtration_gate_blocks()

    @property
    def native_value(self) -> float | int | str | datetime | None:
        """Return the actual sensor value from coordinator data."""
        if self._is_measurement_suppressed():
            return None
        if self._is_production_suppressed():
            return 0
        if self._key == "PH_PUMP_STATUS":
            return decode_ph_pump_status(self.coordinator.data)
        if self._key == "HIDRO_POLARITY":
            return decode_hidro_polarity(self.coordinator.data)
        if self._key == "ION_POLARITY":
            return decode_ion_polarity(self.coordinator.data)
        if self._key == "MBF_PAR_FILT_MODE":
            return self.coordinator.data.get("filtration_mode")
        if self._key == "FILTRATION_SPEED":
            return self.coordinator.data.get("filtration_speed_state")
        if self._key == "MBF_PH_STATUS_ALARM":
            ph_alarm: int | None = self.coordinator.data.get(self._key)
            return PH_STATUS_ALARM_MAP.get(ph_alarm) if ph_alarm is not None else None
        if self._key == "MBF_PAR_INTELLIGENT_TT_NEXT_INTERVAL":
            seconds = self.coordinator.data.get(self._key)
            return calculate_next_interval_time(seconds, self.hass)
        return self.coordinator.data.get(self._key)

    @property
    def options(self) -> list[str] | None:
        """Return the list of options for the sensor."""
        if self._key == "MBF_PAR_FILT_MODE":
            return list(_FILTRATION_MODE_OPTIONS)
        if self._key == "FILTRATION_SPEED":
            return list(_FILTRATION_SPEED_OPTIONS)
        if self._key == "MBF_PH_STATUS_ALARM":
            return list(PH_STATUS_ALARM_MAP.values())
        if self._key == "HIDRO_POLARITY":
            return ["pol1", "pol2", "dead_time", "no_flow", "off"]
        if self._key == "ION_POLARITY":
            return ["pol1", "pol2", "dead_time", "off"]
        if self._key == "PH_PUMP_STATUS":
            relay_ph = self.coordinator.data.get("MBF_PAR_RELAY_PH", 0) or 0
            if relay_ph == 1:
                return ["off", "idle", "acid"]
            if relay_ph == 2:
                return ["off", "idle", "base"]
            return ["off", "idle", "acid", "base", "both"]
        return None  # pragma: no cover


class NeoPoolFiltrationEnergySensor(NeoPoolEntity, RestoreSensor):
    """Cumulative energy consumed by the filtration pump (Wh).

    Integrates instantaneous power over time using coordinator update timestamps.
    Suitable for the Energy dashboard "Individual devices" energy tracking.
    """

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_suggested_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 0
    _attr_translation_key = "filtration_pump_energy"

    def __init__(
        self,
        coordinator: NeoPoolCoordinator,
        entry_id: str,
        pump_power_w: int,
    ) -> None:
        """Initialise the filtration-pump energy sensor."""
        super().__init__(coordinator, entry_id)
        self._pump_power_w = pump_power_w
        device_id = coordinator.entry.unique_id or entry_id
        self._attr_unique_id = f"{device_id}_filtration_pump_energy"
        self._total_wh: float = 0.0
        self._last_update: datetime | None = None
        self._last_pump_on: bool = False

    async def async_added_to_hass(self) -> None:
        """Restore last known energy value from sensor extra data after restart."""
        _LOGGER.debug(
            "ADDED: entity_id=%s, translation_key=%s, has_entity_name=%s",
            self.entity_id,
            self._attr_translation_key,
            getattr(self, "has_entity_name", None),
        )
        await super().async_added_to_hass()
        last_data = await self.async_get_last_sensor_data()
        if last_data is None:  # pragma: no cover
            return
        value = last_data.native_value
        if not isinstance(value, (int, float, str)):  # pragma: no cover
            return
        try:
            restored = float(value)
        except TypeError, ValueError:  # pragma: no cover
            return
        if math.isfinite(restored) and restored >= 0:  # pragma: no cover
            self._total_wh = restored

    def _handle_coordinator_update(self) -> None:
        """Accumulate energy on each coordinator update."""
        now = dt_util.utcnow()
        if self._last_update is not None and self._last_pump_on:
            elapsed_h = (now - self._last_update).total_seconds() / 3600.0
            self._total_wh += self._pump_power_w * elapsed_h
        self._last_update = now
        self._last_pump_on = bool(self.coordinator.data.get("Filtration Pump"))
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> float:
        """Return accumulated energy in Wh."""
        return round(self._total_wh, 3)
