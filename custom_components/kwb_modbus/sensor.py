"""Sensor platform for the KWB Modbus integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import KwbModbusConfigEntry
from .const import (
    CONF_ACTIVE_INSTANCES,
    CONF_DISCOVERED_SENSORS,
    CONF_HEATING_DEVICE,
    CONF_INSTANCE_NAMES,
    DIAGNOSTIC_ADDRESSES,
    DIAGNOSTIC_PARAMS,
    DOMAIN,
    HEATING_DEVICES,
    MODBUS_HOLDING_REG_START,
    SENSOR_STATUS_OK,
    SW_VERSION_ADDRESSES,
)
from .coordinator import KWBDataUpdateCoordinator
from .entity_translations import param_to_translation_key
from .register_maps.types import RegisterDef


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KwbModbusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KWB Modbus sensor entities."""
    coordinator: KWBDataUpdateCoordinator = entry.runtime_data
    discovered: dict[str, bool] = entry.data.get(CONF_DISCOVERED_SENSORS, {})

    # Only create sensor entities for instances the user explicitly configured.
    # Non-indexed sensors (index=None) are always included.
    active_instances: dict[str, list[str]] = entry.data.get(CONF_ACTIVE_INSTANCES, {})
    active_indices: set[str] = {
        instance
        for instances in active_instances.values()
        for instance in instances
    }

    # Flat lookup: instance_label → friendly_name (e.g. "HC 1.1" → "Underfloor heating")
    instance_names: dict[str, str] = {
        inst: name
        for names in entry.data.get(CONF_INSTANCE_NAMES, {}).values()
        for inst, name in names.items()
    }

    all_registers = coordinator.get_all_registers()
    status_addresses: dict[tuple[str, str], int] = {
        (r.param[:-7], r.index): r.address
        for r in all_registers
        if r.is_status and r.param.endswith(".status")
    }

    def _discovered_default(register: RegisterDef) -> bool:
        """Return discovery-driven default enablement for value and status registers."""
        if register.is_status:
            return discovered.get(f"kwb_{register.address - 1}", True)
        return discovered.get(f"kwb_{register.address}", True)

    entities = [
        KWBSensor(
            coordinator,
            r,
            entry,
            _discovered_default(r),
            instance_names,
            None
            if r.is_status
            else status_addresses.get((r.param[:-6], r.index))
            if r.param.endswith(".value")
            else None,
        )
        for r in all_registers
        if (
            r.address not in SW_VERSION_ADDRESSES
            # Writable holding registers are exposed as number/select entities.
            # Read-only holding registers should remain sensors.
            and (
                r.is_status
                or r.address < MODBUS_HOLDING_REG_START
                or (r.address >= MODBUS_HOLDING_REG_START and not r.writable)
            )
        )
        and (not r.index or r.index in active_indices)
    ]

    # Derived helpers for end users: period-based pellet consumption values.
    # These are calculated from the cumulative FS.pelletsverbrauch counter.
    pellet_consumption = next(
        (
            r
            for r in all_registers
            if r.param == "FS.pelletsverbrauch" and not r.index and not r.is_status
        ),
        None,
    )
    if pellet_consumption:
        entities.extend(
            [
                KWBPeriodConsumptionSensor(
                    coordinator,
                    entry,
                    pellet_consumption,
                    period="day",
                    translation_key="fuel_consumption_day",
                ),
                KWBPeriodConsumptionSensor(
                    coordinator,
                    entry,
                    pellet_consumption,
                    period="week",
                    translation_key="fuel_consumption_week",
                ),
                KWBPeriodConsumptionSensor(
                    coordinator,
                    entry,
                    pellet_consumption,
                    period="month",
                    translation_key="fuel_consumption_month",
                ),
                KWBPeriodConsumptionSensor(
                    coordinator,
                    entry,
                    pellet_consumption,
                    period="year",
                    translation_key="fuel_consumption_year",
                ),
            ]
        )
    async_add_entities(entities)


class KWBSensor(CoordinatorEntity[KWBDataUpdateCoordinator], SensorEntity):
    """Sensor entity for a KWB Modbus input register."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KWBDataUpdateCoordinator,
        register: RegisterDef,
        entry: KwbModbusConfigEntry,
        enabled_default: bool,
        instance_names: dict[str, str] | None = None,
        status_address: int | None = None,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator)
        self._register = register
        self._entry = entry
        self._instance_names = instance_names or {}
        self._status_address = status_address
        self._attr_unique_id = f"{entry.entry_id}_{register.address}"
        self._attr_entity_registry_enabled_default = enabled_default
        self._attr_translation_key = param_to_translation_key(register.param)
        if (
            register.address in DIAGNOSTIC_ADDRESSES
            or register.is_status
            or register.param in DIAGNOSTIC_PARAMS
        ):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        unit = register.unit
        if register.value_table:
            # ENUM sensors must not have a unit of measurement
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(
                coordinator.get_value_table(register.value_table).values()
            )
        elif unit == "°C":
            self._attr_native_unit_of_measurement = unit
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit == "kW":
            self._attr_native_unit_of_measurement = unit
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit == "kWh":
            self._attr_native_unit_of_measurement = unit
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif unit == "%":
            self._attr_native_unit_of_measurement = unit
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit:
            self._attr_native_unit_of_measurement = unit

    @property
    def available(self) -> bool:
        """Return availability based on coordinator and optional status register."""
        if not super().available:
            return False
        data = self.coordinator.data or {}
        if self._register.is_status:
            return data.get(self._register.address) is not None
        if self._status_address is None:
            return True
        status = data.get(self._status_address)
        return status in (SENSOR_STATUS_OK, "OK")

    @property
    def native_value(self) -> Any:
        """Return the current sensor value."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._register.address)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "modbus_address": self._register.address,
            "kwb_parameter": self._register.param,
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information.

        Indexed entities (HC, BUF, SOL, ...) are attached to a per-instance
        sub-device that is linked to the main KWB boiler device via via_device.
        Non-indexed entities live directly on the main device.
        """
        if self._register.index:
            friendly_name = self._instance_names.get(
                self._register.index, self._register.index
            )
            return DeviceInfo(
                identifiers={(DOMAIN, f"{self._entry.entry_id}_{self._register.index}")},
                name=friendly_name,
                via_device=(DOMAIN, self._entry.entry_id),
                manufacturer="KWB",
            )
        model = HEATING_DEVICES.get(self._entry.data.get(CONF_HEATING_DEVICE, ""), "KWB Heating")
        data = self.coordinator.data or {}
        major, minor, patch = data.get(8192), data.get(8193), data.get(8194)
        sw_version = (
            f"{major}.{minor}.{patch}" if None not in (major, minor, patch) else None
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=model,
            manufacturer="KWB",
            model=model,
            sw_version=sw_version,
        )


class KWBPeriodConsumptionSensor(
    CoordinatorEntity[KWBDataUpdateCoordinator], SensorEntity, RestoreEntity
):
    """Derived period consumption sensor based on a cumulative pellet counter."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KWBDataUpdateCoordinator,
        entry: KwbModbusConfigEntry,
        source_register: RegisterDef,
        period: str,
        translation_key: str,
    ) -> None:
        """Initialize the derived period consumption sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._source_register = source_register
        self._period = period
        self._period_key: str | None = None
        self._period_start_total: float | None = None
        self._period_started_at: str | None = None
        self._native_value: float | None = None
        self._attr_unique_id = f"{entry.entry_id}_{source_register.param}_{period}"
        self._attr_translation_key = translation_key
        self._attr_native_unit_of_measurement = "kg"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_suggested_display_precision = 1
        self._attr_icon = "mdi:fire"

    async def async_added_to_hass(self) -> None:
        """Restore state so values survive restarts."""
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            if last_state.state not in ("unknown", "unavailable"):
                try:
                    self._native_value = float(last_state.state)
                except ValueError:
                    self._native_value = None
            if "period_key" in last_state.attributes:
                self._period_key = str(last_state.attributes["period_key"])
            if "period_start_total" in last_state.attributes:
                try:
                    self._period_start_total = float(last_state.attributes["period_start_total"])
                except (TypeError, ValueError):
                    self._period_start_total = None
            if "period_started_at" in last_state.attributes:
                self._period_started_at = str(last_state.attributes["period_started_at"])
        self._recalculate()

    def _current_period_key(self) -> str:
        """Return a stable key for the current time period."""
        now = dt_util.now()
        if self._period == "day":
            return now.strftime("%Y-%m-%d")
        if self._period == "week":
            iso = now.isocalendar()
            return f"{iso.year}-W{iso.week:02d}"
        if self._period == "month":
            return now.strftime("%Y-%m")
        return now.strftime("%Y")

    def _period_start_iso(self) -> str:
        """Return ISO timestamp representing the start of the current period."""
        now = dt_util.now()
        if self._period == "day":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif self._period == "week":
            start = (now - timedelta(days=now.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif self._period == "month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return start.isoformat()

    def _recalculate(self) -> None:
        """Recalculate the derived value based on current cumulative total."""
        data = self.coordinator.data or {}
        raw_total = data.get(self._source_register.address)
        if raw_total is None:
            self._native_value = None
            return
        total = float(raw_total)
        period_key = self._current_period_key()
        if self._period_key != period_key:
            self._period_key = period_key
            self._period_start_total = total
            self._period_started_at = self._period_start_iso()
        elif self._period_start_total is None or total < self._period_start_total:
            # Handle first run and counter resets without negative deltas.
            self._period_start_total = total

        self._native_value = max(0.0, total - self._period_start_total)

    @property
    def available(self) -> bool:
        """Return availability based on source register."""
        if not super().available:
            return False
        data = self.coordinator.data or {}
        return data.get(self._source_register.address) is not None

    @property
    def native_value(self) -> float | None:
        """Return the current derived period consumption."""
        return self._native_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes for diagnostics."""
        return {
            "source_modbus_address": self._source_register.address,
            "source_kwb_parameter": self._source_register.param,
            "period_key": self._period_key,
            "period_start_total": self._period_start_total,
            "period_started_at": self._period_started_at,
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Attach derived sensors to the main KWB device."""
        model = HEATING_DEVICES.get(self._entry.data.get(CONF_HEATING_DEVICE, ""), "KWB Heating")
        data = self.coordinator.data or {}
        major, minor, patch = data.get(8192), data.get(8193), data.get(8194)
        sw_version = (
            f"{major}.{minor}.{patch}" if None not in (major, minor, patch) else None
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=model,
            manufacturer="KWB",
            model=model,
            sw_version=sw_version,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update derived value when fresh Modbus data arrives."""
        self._recalculate()
        self.async_write_ha_state()
