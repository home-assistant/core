"""Sensor platform for SunSynk integration."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SunSynkConfigEntry, SunSynkCoordinator
from .const import DOMAIN
from .helpers import (
    extract_value,
    get_inv_data,
    get_source_obj,
    inverter_device_info,
    safe_float,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


# ---------------------------------------------------------------------------
# Base sensor
# ---------------------------------------------------------------------------


class SunSynkBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for SunSynk sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SunSynkCoordinator,
        unique_id_suffix: str,
        translation_key: str,
        unit: str | None = None,
        device_class: SensorDeviceClass | None = None,
        state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT,
    ) -> None:
        """Initialise the base sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{unique_id_suffix}"
        self._attr_translation_key = translation_key
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    def _compute_native_value(self) -> Any:
        """Compute the native value from coordinator data. Override in subclasses."""
        return None

    def _compute_extra_state_attributes(self) -> dict[str, Any] | None:
        """Compute extra state attributes. Override in subclasses."""
        return None

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        was_available = getattr(self, "_attr_available", True)
        self._attr_available = self.coordinator.last_update_success
        if was_available and not self._attr_available:
            _LOGGER.warning(
                "Entity %s is now unavailable",
                self._attr_unique_id,
            )
        self._attr_native_value = self._compute_native_value()
        self._attr_extra_state_attributes = self._compute_extra_state_attributes() or {}
        super()._handle_coordinator_update()


# ---------------------------------------------------------------------------
# Gateway sensor
# ---------------------------------------------------------------------------


class SunSynkGatewaySensor(SunSynkBaseSensor):
    """Sensor for SunSynk gateway status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SunSynkCoordinator,
        gateway: Any,
        key: str,
        translation_key: str,
        **kwargs: Any,
    ) -> None:
        """Initialise the gateway sensor."""
        super().__init__(
            coordinator, f"gateway_{gateway.sn}_{key}", translation_key, **kwargs
        )
        self._gateway_sn = gateway.sn
        self._key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"gateway_{gateway.sn}")},
            name=f"SunSynk Gateway {gateway.sn}",
            manufacturer="SunSynk",
            model="Gateway",
            serial_number=gateway.sn,
        )

    def _compute_native_value(self) -> Any | None:
        """Return the current value."""
        if not self.coordinator.data:
            return None
        gateways = self.coordinator.data.get("gateways", [])
        for gw in gateways:
            if gw.sn == self._gateway_sn:
                return getattr(gw, self._key, None)
        return None


# ---------------------------------------------------------------------------
# Event sensor
# ---------------------------------------------------------------------------


class SunSynkEventSensor(SunSynkBaseSensor):
    """Sensor for SunSynk event counts with detail attributes."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: SunSynkCoordinator, type_id: int, translation_key: str
    ) -> None:
        """Initialise the event sensor."""
        super().__init__(
            coordinator,
            f"events_{type_id}",
            translation_key,
            state_class=SensorStateClass.TOTAL,
        )
        self._type_id = type_id

    def _compute_native_value(self) -> int:
        """Return the event count."""
        if not self.coordinator.data:
            return 0
        events = self.coordinator.data.get("events", {}).get(self._type_id, [])
        return len(events) if events else 0

    def _compute_extra_state_attributes(self) -> dict[str, Any] | None:
        """Return event detail list as attributes."""
        if not self.coordinator.data:
            return None
        events = self.coordinator.data.get("events", {}).get(self._type_id, [])
        if not events:
            return None
        details: list[str] = []
        for e in events:
            time_val = getattr(e, "time", None) or extract_value(e, "time")
            sn_val = getattr(e, "sn", None) or extract_value(e, "sn")
            code = getattr(e, "event_code", None) or extract_value(e, "eventCode")
            desc = getattr(e, "event_description", None) or extract_value(
                e, "eventDescription"
            )
            if time_val or sn_val or code or desc:
                details.append(f"{time_val} - {sn_val} - {code} - {desc}")
        if details:
            return {"events": details}
        return None


# ---------------------------------------------------------------------------
# Plant flow sensor
# ---------------------------------------------------------------------------


class SunSynkPlantFlowSensor(SunSynkBaseSensor):
    """Sensor for SunSynk plant energy flow."""

    def __init__(
        self,
        coordinator: SunSynkCoordinator,
        plant_id: int,
        key: str,
        translation_key: str,
        unit: str,
        device_class: SensorDeviceClass,
    ) -> None:
        """Initialise the plant flow sensor."""
        super().__init__(
            coordinator,
            f"plant_{plant_id}_flow_{key}",
            translation_key,
            unit,
            device_class,
        )
        self._plant_id = plant_id
        self._key = key
        plant_info = (
            coordinator.data.get("plants", {}).get(plant_id, {}).get("info")
            if coordinator.data
            else None
        )
        plant_name = getattr(plant_info, "name", None) or f"Plant {plant_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"plant_{plant_id}")},
            name=f"SunSynk {plant_name}",
            manufacturer="SunSynk",
            model="Solar Plant",
        )

    def _compute_native_value(self) -> Any | None:
        """Return the current value."""
        if not self.coordinator.data:
            return None
        plant = self.coordinator.data.get("plants", {}).get(self._plant_id)
        if plant and plant.get("flow"):
            return getattr(plant["flow"], self._key, None)
        return None


# ---------------------------------------------------------------------------
# Inverter sensor (simple key-from-source)
# ---------------------------------------------------------------------------


class SunSynkInverterSensor(SunSynkBaseSensor):
    """Sensor for SunSynk inverter data."""

    def __init__(
        self,
        coordinator: SunSynkCoordinator,
        plant_id: int,
        sn: str,
        key: str,
        translation_key: str,
        source_type: str,
        unit: str | None,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT,
    ) -> None:
        """Initialise the inverter sensor."""
        super().__init__(
            coordinator,
            f"inverter_{sn}_{source_type}_{key}",
            translation_key,
            unit,
            device_class,
            state_class,
        )
        self._plant_id = plant_id
        self._sn = sn
        self._key = key
        self._source_type = source_type
        self._attr_device_info = inverter_device_info(plant_id, sn)

    def _compute_native_value(self) -> Any | None:
        """Return the current value."""
        source_obj = get_source_obj(
            self.coordinator,
            self._plant_id,
            self._sn,
            self._source_type,
        )
        if not source_obj:
            return None
        return getattr(source_obj, self._key, None)


class SunSynkInverterSettingsSensor(SunSynkInverterSensor):
    """Read-only sensor mirroring an inverter setting (disabled by default)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False


# ---------------------------------------------------------------------------
# Inverter temperature sensor
# ---------------------------------------------------------------------------


class SunSynkInverterTempSensor(SunSynkBaseSensor):
    """Sensor for SunSynk inverter temperatures."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SunSynkCoordinator,
        plant_id: int,
        sn: str,
        key: str,
        translation_key: str,
        unit: str,
        device_class: SensorDeviceClass,
    ) -> None:
        """Initialise the inverter temperature sensor."""
        super().__init__(
            coordinator,
            f"inverter_{sn}_temp_{key}",
            translation_key,
            unit,
            device_class,
        )
        self._plant_id = plant_id
        self._sn = sn
        self._key = key
        self._attr_device_info = inverter_device_info(plant_id, sn)

    def _compute_native_value(self) -> float | None:
        """Return the current value."""
        latest = self._get_latest_temp_record()
        if latest is None:
            return None

        val = extract_value(latest, self._key)
        return safe_float(val)

    def _get_latest_temp_record(self) -> Any | None:
        """Return the most recent temperature record for this inverter."""
        day_res = get_source_obj(
            self.coordinator,
            self._plant_id,
            self._sn,
            "temp",
        )
        if not day_res or not day_res.infos:
            return None
        return day_res.infos[-1]


# ---------------------------------------------------------------------------
# VIP (voltage/current/power from vip[] lists) sensor
# ---------------------------------------------------------------------------


class SunSynkVipSensor(SunSynkBaseSensor):
    """Sensor reading voltage/current/power from a source's vip list."""

    def __init__(
        self,
        coordinator: SunSynkCoordinator,
        plant_id: int,
        sn: str,
        source_type: str,
        vip_index: int,
        vip_field: str,
        translation_key: str,
        unit: str,
        device_class: SensorDeviceClass,
    ) -> None:
        """Initialise the VIP sensor."""
        super().__init__(
            coordinator,
            f"inverter_{sn}_{source_type}_vip{vip_index}_{vip_field}",
            translation_key,
            unit,
            device_class,
        )
        self._plant_id = plant_id
        self._sn = sn
        self._source_type = source_type
        self._vip_index = vip_index
        self._vip_field = vip_field
        self._attr_device_info = inverter_device_info(plant_id, sn)

    def _compute_native_value(self) -> float | None:
        """Return the current value."""
        source_obj = get_source_obj(
            self.coordinator,
            self._plant_id,
            self._sn,
            self._source_type,
        )
        if not source_obj:
            return None
        vip_list = getattr(source_obj, "vip", None)
        if not vip_list or len(vip_list) <= self._vip_index:
            return None
        return safe_float(getattr(vip_list[self._vip_index], self._vip_field, None))


# ---------------------------------------------------------------------------
# PV string sensor (from input.pv_iv list)
# ---------------------------------------------------------------------------


class SunSynkPvStringSensor(SunSynkBaseSensor):
    """Sensor for individual PV string data from input.pv_iv[]."""

    def __init__(
        self,
        coordinator: SunSynkCoordinator,
        plant_id: int,
        sn: str,
        string_index: int,
        field: str,
        translation_key: str,
        unit: str,
        device_class: SensorDeviceClass,
    ) -> None:
        """Initialise the PV string sensor."""
        super().__init__(
            coordinator,
            f"inverter_{sn}_pv{string_index + 1}_{field}",
            translation_key,
            unit,
            device_class,
        )
        self._attr_translation_placeholders = {"string_num": str(string_index + 1)}
        self._plant_id = plant_id
        self._sn = sn
        self._string_index = string_index
        self._field = field
        self._attr_device_info = inverter_device_info(plant_id, sn)

    def _compute_native_value(self) -> float | None:
        """Return the current value."""
        source_obj = get_source_obj(
            self.coordinator,
            self._plant_id,
            self._sn,
            "input",
        )
        if not source_obj:
            return None
        pv_iv = getattr(source_obj, "pv_iv", None)
        if not pv_iv or len(pv_iv) <= self._string_index:
            return None
        return safe_float(getattr(pv_iv[self._string_index], self._field, None))


# ---------------------------------------------------------------------------
# Computed sensor (value derived from multiple fields)
# ---------------------------------------------------------------------------


class SunSynkComputedSensor(SunSynkBaseSensor):
    """Sensor whose value is computed from multiple coordinator data fields."""

    def __init__(
        self,
        coordinator: SunSynkCoordinator,
        plant_id: int,
        sn: str,
        unique_key: str,
        translation_key: str,
        compute_fn: Callable[[dict[str, Any]], float | None],
        unit: str | None,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT,
    ) -> None:
        """Initialise the computed sensor."""
        super().__init__(
            coordinator,
            f"inverter_{sn}_computed_{unique_key}",
            translation_key,
            unit,
            device_class,
            state_class,
        )
        self._plant_id = plant_id
        self._sn = sn
        self._compute_fn = compute_fn
        self._attr_device_info = inverter_device_info(plant_id, sn)

    def _compute_native_value(self) -> float | None:
        """Return the computed value."""
        inv_data = get_inv_data(self.coordinator, self._plant_id, self._sn)
        if not inv_data:
            return None
        try:
            val = self._compute_fn(inv_data)
            return safe_float(val)
        except TypeError, AttributeError, ZeroDivisionError, IndexError:
            return None


# ---------------------------------------------------------------------------
# Notification sensor
# ---------------------------------------------------------------------------


class SunSynkNotificationSensor(SunSynkBaseSensor):
    """Sensor for SunSynk notifications with detail attributes."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SunSynkCoordinator) -> None:
        """Initialise the notification sensor."""
        super().__init__(
            coordinator,
            "notifications",
            "notifications",
            state_class=SensorStateClass.TOTAL,
        )

    def _compute_native_value(self) -> int:
        """Return the notification count."""
        if not self.coordinator.data:
            return 0
        notifications = self.coordinator.data.get("notifications", [])
        return len(notifications) if notifications else 0

    def _compute_extra_state_attributes(self) -> dict[str, Any] | None:
        """Return notification detail list as attributes."""
        if not self.coordinator.data:
            return None
        notifications = self.coordinator.data.get("notifications", [])
        if not notifications:
            return None
        details: list[str] = []
        for n in notifications:
            create_at = getattr(n, "create_at", None) or extract_value(n, "createAt")
            desc = getattr(n, "description", None) or extract_value(n, "description")
            station = getattr(n, "station_name", None) or extract_value(
                n, "stationName"
            )
            if create_at or desc:
                text = desc or ""
                if station:
                    text = text.replace("(#{stationName})", f"{station} ")
                details.append(f"{create_at} - {text}")
        if details:
            return {"notifications": details}
        return None


# ---------------------------------------------------------------------------
# Error tracking sensor
# ---------------------------------------------------------------------------


class SunSynkErrorSensor(SunSynkBaseSensor):
    """Sensor exposing API error counts per category."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SunSynkCoordinator) -> None:
        """Initialise the error sensor."""
        super().__init__(coordinator, "errors", "api_errors", state_class=None)

    def _compute_native_value(self) -> int:
        """Return total error count across all categories."""
        if not self.coordinator.data:
            return 0
        errors = self.coordinator.data.get("errors", {})
        return sum(info.get("count", 0) for info in errors.values())

    def _compute_extra_state_attributes(self) -> dict[str, Any] | None:
        """Return flattened error tracking data as attributes."""
        if not self.coordinator.data:
            return None
        errors = self.coordinator.data.get("errors")
        if not errors:
            return None
        attrs: dict[str, Any] = {}
        for cat, info in errors.items():
            attrs[f"{cat}_count"] = info.get("count", 0)
            attrs[f"{cat}_payload"] = info.get("payload", "")
            attrs[f"{cat}_date"] = info.get("date", "")
        return attrs


# ---------------------------------------------------------------------------
# Last update timestamp sensor
# ---------------------------------------------------------------------------


class SunSynkLastUpdateSensor(SunSynkBaseSensor):
    """Sensor showing when data was last successfully fetched."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SunSynkCoordinator) -> None:
        """Initialise the last update sensor."""
        super().__init__(
            coordinator,
            "stats_last_update",
            "stats_last_update",
            device_class=SensorDeviceClass.TIMESTAMP,
            state_class=None,
        )

    def _compute_native_value(self) -> Any | None:
        """Return the last update as a timezone-aware datetime."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("last_update")


# ---------------------------------------------------------------------------
# Consolidated plant sensor (aggregates across all inverters)
# ---------------------------------------------------------------------------


class SunSynkConsolidatedSensor(SunSynkBaseSensor):
    """Sensor that sums a field across all inverters in a plant."""

    def __init__(
        self,
        coordinator: SunSynkCoordinator,
        plant_id: int,
        source_type: str,
        key: str,
        translation_key: str,
        unit: str | None,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT,
    ) -> None:
        """Initialise the consolidated sensor."""
        super().__init__(
            coordinator,
            f"plant_{plant_id}_consolidated_{source_type}_{key}",
            translation_key,
            unit,
            device_class,
            state_class,
        )
        self._plant_id = plant_id
        self._source_type = source_type
        self._key = key
        plant_info = (
            coordinator.data.get("plants", {}).get(plant_id, {}).get("info")
            if coordinator.data
            else None
        )
        plant_name = getattr(plant_info, "name", None) or f"Plant {plant_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"plant_{plant_id}")},
            name=f"SunSynk {plant_name}",
            manufacturer="SunSynk",
            model="Solar Plant",
        )

    def _compute_native_value(self) -> float | None:
        """Return the summed value across all inverters."""
        if not self.coordinator.data:
            return None
        plant = self.coordinator.data.get("plants", {}).get(self._plant_id)
        if not plant:
            return None
        total = 0.0
        found_any = False
        for inv_data in plant.get("inverters", {}).values():
            source = inv_data.get(self._source_type)
            if not source:
                continue
            val = safe_float(getattr(source, self._key, None))
            if val is not None:
                total += val
                found_any = True
        return round(total, 3) if found_any else None


# ---------------------------------------------------------------------------
# Helper: compute internal power usage for usable inverter sensor
# ---------------------------------------------------------------------------


def _compute_internal_power_usage(
    coordinator: SunSynkCoordinator,
    plant_id: int,
    sn: str,
) -> float | None:
    """Return internal power usage: pv + grid + battery - load."""
    inv_data = get_inv_data(coordinator, plant_id, sn)
    if not inv_data:
        return None
    pv = safe_float(getattr(inv_data.get("input"), "pac", None))
    grid = safe_float(getattr(inv_data.get("grid"), "pac", None))
    batt = safe_float(getattr(inv_data.get("battery"), "power", None))
    load = safe_float(getattr(inv_data.get("load"), "total_power", None))
    if pv is None or grid is None or batt is None or load is None:
        return None
    return round(pv + grid + batt - load, 3)


# ---------------------------------------------------------------------------
# Raw data sensor helpers
# ---------------------------------------------------------------------------

_RAW_SENSOR_DEFAULTS: dict[str, dict[str, Any]] = {
    "grid": {"power": 0, "gridonline": 0},
    "load": {"power": 0},
    "output": {"internalpowerusage": 0},
    "battery": {"soc": 0, "power": 0},
    "input": {"power": 0, "1_power": 0, "2_power": 0},
    "temp": {"battery": 0, "ac": 0, "dc": 0},
}


def _apply_source_aliases(
    attrs: dict[str, Any],
    source_type: str,
    coordinator: SunSynkCoordinator,
    plant_id: int,
    sn: str,
) -> None:
    """Apply legacy alias keys to raw sensor attributes in place."""
    if source_type == "grid":
        attrs["power"] = attrs.get("pac", 0)
        attrs["gridonline"] = attrs.get("status", 0)
    elif source_type == "load":
        attrs["power"] = attrs.get("total_power", 0)
    elif source_type == "output":
        attrs["internalpowerusage"] = (
            _compute_internal_power_usage(
                coordinator,
                plant_id,
                sn,
            )
            or 0
        )
    elif source_type == "input":
        attrs["power"] = attrs.get("pac", 0)
        pv_iv: list[Any] = attrs.get("pv_iv") or []
        attrs["1_power"] = pv_iv[0].get("ppv", 0) if len(pv_iv) > 0 else 0
        attrs["2_power"] = pv_iv[1].get("ppv", 0) if len(pv_iv) > 1 else 0


# ---------------------------------------------------------------------------
# Raw data sensor (replicates old "usable" container sensor contract)
# ---------------------------------------------------------------------------


class SunSynkRawDataSensor(SunSynkBaseSensor):
    """Exposes all fields of an API response object as state attributes.

    Replicates the old 'sunsynk_usable_*' sensor contract so that
    existing template sensors in configuration.yaml continue to work.
    """

    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: SunSynkCoordinator,
        plant_id: int,
        sn: str,
        source_type: str,
        name: str,
    ) -> None:
        """Initialise the raw data sensor."""
        super().__init__(
            coordinator,
            f"usable_{source_type}",
            f"raw_{source_type}",
            state_class=None,
        )
        self._attr_translation_key = None
        self._attr_name = name
        self._plant_id = plant_id
        self._sn = sn
        self._source_type = source_type
        self._attr_device_info = inverter_device_info(plant_id, sn)

    def _compute_native_value(self) -> str | None:
        """Return 'ok' when data is available, else None."""
        source = get_source_obj(
            self.coordinator,
            self._plant_id,
            self._sn,
            self._source_type,
        )
        return "ok" if source else None

    def _compute_extra_state_attributes(self) -> dict[str, Any] | None:
        """Return all response fields as flat attributes with legacy aliases."""
        defaults = _RAW_SENSOR_DEFAULTS.get(self._source_type, {})

        if self._source_type == "temp":
            return self._compute_temp_attributes(dict(defaults))

        source = get_source_obj(
            self.coordinator,
            self._plant_id,
            self._sn,
            self._source_type,
        )
        if not source:
            return dict(defaults)

        dumped: dict[str, Any] = (
            source.model_dump()
            if hasattr(source, "model_dump")
            else dict(source.__dict__)
        )
        # Merge: defaults first, then dumped on top — ensures keys stripped
        # by model_serializer (None optionals) still have fallback values.
        attrs = {**defaults, **dumped}
        _apply_source_aliases(
            attrs, self._source_type, self.coordinator, self._plant_id, self._sn
        )
        return attrs

    def _compute_temp_attributes(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Compute composite temperature attributes from temp + battery sources."""
        temp_source = get_source_obj(
            self.coordinator,
            self._plant_id,
            self._sn,
            "temp",
        )
        if temp_source and hasattr(temp_source, "infos") and temp_source.infos:
            latest = temp_source.infos[-1]
            dc_val = safe_float(getattr(latest, "dc_temp", None))
            ac_val = safe_float(getattr(latest, "igbt_temp", None))
            if dc_val is not None:
                attrs["dc"] = dc_val
            if ac_val is not None:
                attrs["ac"] = ac_val
        batt_source = get_source_obj(
            self.coordinator,
            self._plant_id,
            self._sn,
            "battery",
        )
        if batt_source:
            batt_temp = safe_float(getattr(batt_source, "temp", None))
            if batt_temp is not None:
                attrs["battery"] = batt_temp
        return attrs


# ---------------------------------------------------------------------------
# Factory: gateway sensors
# ---------------------------------------------------------------------------


def _create_gateway_sensors(
    coordinator: SunSynkCoordinator,
    gateways: list[Any],
) -> list[SensorEntity]:
    """Create sensor entities for gateways."""
    entities: list[SensorEntity] = []
    for gw in gateways:
        entities.append(
            SunSynkGatewaySensor(coordinator, gw, "status", "gateway_status")
        )
        entities.append(
            SunSynkGatewaySensor(
                coordinator,
                gw,
                "signal",
                "gateway_signal",
                state_class=SensorStateClass.MEASUREMENT,
                unit=None,
            )
        )
    return entities


# ---------------------------------------------------------------------------
# Factory: plant flow sensors
# ---------------------------------------------------------------------------


def _create_plant_flow_sensors(
    coordinator: SunSynkCoordinator,
    plant_id: int,
) -> list[SensorEntity]:
    """Create sensor entities for plant energy flow."""
    flow_defs: list[tuple[str, str, str, SensorDeviceClass]] = [
        ("pv_power", "plant_pv_power", UnitOfPower.WATT, SensorDeviceClass.POWER),
        (
            "batt_power",
            "plant_battery_power",
            UnitOfPower.WATT,
            SensorDeviceClass.POWER,
        ),
        (
            "grid_or_meter_power",
            "plant_grid_power",
            UnitOfPower.WATT,
            SensorDeviceClass.POWER,
        ),
        (
            "load_or_eps_power",
            "plant_load_power",
            UnitOfPower.WATT,
            SensorDeviceClass.POWER,
        ),
        ("soc", "plant_soc", PERCENTAGE, SensorDeviceClass.BATTERY),
        (
            "gen_power",
            "plant_generator_power",
            UnitOfPower.WATT,
            SensorDeviceClass.POWER,
        ),
        ("min_power", "plant_min_power", UnitOfPower.WATT, SensorDeviceClass.POWER),
        (
            "smart_load_power",
            "plant_smart_load_power",
            UnitOfPower.WATT,
            SensorDeviceClass.POWER,
        ),
        (
            "home_load_power",
            "plant_home_load_power",
            UnitOfPower.WATT,
            SensorDeviceClass.POWER,
        ),
        (
            "ups_load_power",
            "plant_ups_load_power",
            UnitOfPower.WATT,
            SensorDeviceClass.POWER,
        ),
    ]
    return [
        SunSynkPlantFlowSensor(coordinator, plant_id, key, tkey, unit, dc)
        for key, tkey, unit, dc in flow_defs
    ]


# ---------------------------------------------------------------------------
# Factory: inverter sensors
# ---------------------------------------------------------------------------


def _create_inverter_sensors(
    coordinator: SunSynkCoordinator,
    plant_id: int,
    sn: str,
    inv_data: dict[str, Any],
) -> list[SensorEntity]:
    """Create sensor entities for a single inverter."""
    entities: list[SensorEntity] = [
        SunSynkInverterSensor(
            coordinator,
            plant_id,
            sn,
            "pac",
            "inverter_power_output",
            "info",
            UnitOfPower.KILO_WATT,
            SensorDeviceClass.POWER,
        ),
    ]

    # --- Battery sensors ---
    if inv_data.get("battery"):
        batt_defs: list[
            tuple[
                str, str, str | None, SensorDeviceClass | None, SensorStateClass | None
            ]
        ] = [
            (
                "soc",
                "battery_soc",
                PERCENTAGE,
                SensorDeviceClass.BATTERY,
                SensorStateClass.MEASUREMENT,
            ),
            (
                "voltage",
                "battery_voltage",
                UnitOfElectricPotential.VOLT,
                SensorDeviceClass.VOLTAGE,
                SensorStateClass.MEASUREMENT,
            ),
            (
                "charge_volt",
                "battery_charge_voltage",
                UnitOfElectricPotential.VOLT,
                SensorDeviceClass.VOLTAGE,
                SensorStateClass.MEASUREMENT,
            ),
            ("status", "battery_status", None, None, None),
            (
                "charge_current_limit",
                "battery_charge_current_limit",
                UnitOfElectricCurrent.AMPERE,
                SensorDeviceClass.CURRENT,
                SensorStateClass.MEASUREMENT,
            ),
            (
                "discharge_current_limit",
                "battery_discharge_current_limit",
                UnitOfElectricCurrent.AMPERE,
                SensorDeviceClass.CURRENT,
                SensorStateClass.MEASUREMENT,
            ),
            (
                "correct_cap",
                "battery_capacity",
                UnitOfEnergy.KILO_WATT_HOUR,
                None,
                None,
            ),
            (
                "current",
                "battery_current",
                UnitOfElectricCurrent.AMPERE,
                SensorDeviceClass.CURRENT,
                SensorStateClass.MEASUREMENT,
            ),
            (
                "power",
                "battery_power",
                UnitOfPower.KILO_WATT,
                SensorDeviceClass.POWER,
                SensorStateClass.MEASUREMENT,
            ),
            (
                "etotal_chg",
                "battery_total_charge",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL,
            ),
            (
                "etotal_dischg",
                "battery_total_discharge",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL,
            ),
            (
                "etoday_chg",
                "battery_today_charge",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL,
            ),
            (
                "etoday_dischg",
                "battery_today_discharge",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL,
            ),
            (
                "temp",
                "battery_temperature",
                UnitOfTemperature.CELSIUS,
                SensorDeviceClass.TEMPERATURE,
                SensorStateClass.MEASUREMENT,
            ),
        ]
        for key, tkey, unit, dc, sc in batt_defs:
            entities.append(
                SunSynkInverterSensor(
                    coordinator,
                    plant_id,
                    sn,
                    key,
                    tkey,
                    "battery",
                    unit,
                    dc,
                    sc,
                )
            )

    # --- Grid sensors ---
    if inv_data.get("grid"):
        grid_defs: list[
            tuple[
                str, str, str | None, SensorDeviceClass | None, SensorStateClass | None
            ]
        ] = [
            (
                "pac",
                "grid_power",
                UnitOfPower.KILO_WATT,
                SensorDeviceClass.POWER,
                SensorStateClass.MEASUREMENT,
            ),
            (
                "fac",
                "grid_frequency",
                UnitOfFrequency.HERTZ,
                SensorDeviceClass.FREQUENCY,
                SensorStateClass.MEASUREMENT,
            ),
            ("status", "grid_status", None, None, None),
            (
                "pf",
                "grid_power_factor",
                None,
                SensorDeviceClass.POWER_FACTOR,
                SensorStateClass.MEASUREMENT,
            ),
            (
                "etotal_from",
                "grid_total_import",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL,
            ),
            (
                "etotal_to",
                "grid_total_export",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL,
            ),
            (
                "etoday_from",
                "grid_today_import",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL,
            ),
            (
                "etoday_to",
                "grid_today_export",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL,
            ),
            (
                "limiter_total_power",
                "grid_limiter_total_power",
                UnitOfPower.KILO_WATT,
                SensorDeviceClass.POWER,
                SensorStateClass.MEASUREMENT,
            ),
        ]
        for key, tkey, unit, dc, sc in grid_defs:
            entities.append(
                SunSynkInverterSensor(
                    coordinator,
                    plant_id,
                    sn,
                    key,
                    tkey,
                    "grid",
                    unit,
                    dc,
                    sc,
                )
            )
        # Grid voltage from vip[0]
        entities.append(
            SunSynkVipSensor(
                coordinator,
                plant_id,
                sn,
                "grid",
                0,
                "volt",
                "grid_voltage",
                UnitOfElectricPotential.VOLT,
                SensorDeviceClass.VOLTAGE,
            )
        )

    # --- Load sensors ---
    if inv_data.get("load"):
        load_defs: list[
            tuple[
                str, str, str | None, SensorDeviceClass | None, SensorStateClass | None
            ]
        ] = [
            (
                "total_power",
                "load_power",
                UnitOfPower.KILO_WATT,
                SensorDeviceClass.POWER,
                SensorStateClass.MEASUREMENT,
            ),
            (
                "total_used",
                "load_total_used",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL,
            ),
            (
                "daily_used",
                "load_daily_used",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL,
            ),
            (
                "load_fac",
                "load_frequency",
                UnitOfFrequency.HERTZ,
                SensorDeviceClass.FREQUENCY,
                SensorStateClass.MEASUREMENT,
            ),
            ("smart_load_status", "smart_load_status", None, None, None),
            (
                "ups_power_total",
                "load_ups_power",
                UnitOfPower.KILO_WATT,
                SensorDeviceClass.POWER,
                SensorStateClass.MEASUREMENT,
            ),
        ]
        for key, tkey, unit, dc, sc in load_defs:
            entities.append(
                SunSynkInverterSensor(
                    coordinator,
                    plant_id,
                    sn,
                    key,
                    tkey,
                    "load",
                    unit,
                    dc,
                    sc,
                )
            )
        # Load voltage from vip[0]
        entities.append(
            SunSynkVipSensor(
                coordinator,
                plant_id,
                sn,
                "load",
                0,
                "volt",
                "load_voltage",
                UnitOfElectricPotential.VOLT,
                SensorDeviceClass.VOLTAGE,
            )
        )

    # --- Output sensors ---
    if inv_data.get("output"):
        output_defs: list[
            tuple[
                str, str, str | None, SensorDeviceClass | None, SensorStateClass | None
            ]
        ] = [
            (
                "p_inv",
                "inverter_power",
                UnitOfPower.KILO_WATT,
                SensorDeviceClass.POWER,
                SensorStateClass.MEASUREMENT,
            ),
            (
                "fac",
                "output_frequency",
                UnitOfFrequency.HERTZ,
                SensorDeviceClass.FREQUENCY,
                SensorStateClass.MEASUREMENT,
            ),
        ]
        for key, tkey, unit, dc, sc in output_defs:
            entities.append(
                SunSynkInverterSensor(
                    coordinator,
                    plant_id,
                    sn,
                    key,
                    tkey,
                    "output",
                    unit,
                    dc,
                    sc,
                )
            )
        # Output voltage from vip[0]
        entities.append(
            SunSynkVipSensor(
                coordinator,
                plant_id,
                sn,
                "output",
                0,
                "volt",
                "output_voltage",
                UnitOfElectricPotential.VOLT,
                SensorDeviceClass.VOLTAGE,
            )
        )

    # --- Generator sensors ---
    if inv_data.get("gen"):
        gen_defs: list[
            tuple[
                str, str, str | None, SensorDeviceClass | None, SensorStateClass | None
            ]
        ] = [
            (
                "gen_total",
                "generator_total_energy",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL,
            ),
            (
                "gen_daily",
                "generator_daily_energy",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL,
            ),
            (
                "total_power",
                "generator_power",
                UnitOfPower.KILO_WATT,
                SensorDeviceClass.POWER,
                SensorStateClass.MEASUREMENT,
            ),
            (
                "gen_fac",
                "generator_frequency",
                UnitOfFrequency.HERTZ,
                SensorDeviceClass.FREQUENCY,
                SensorStateClass.MEASUREMENT,
            ),
        ]
        for key, tkey, unit, dc, sc in gen_defs:
            entities.append(
                SunSynkInverterSensor(
                    coordinator,
                    plant_id,
                    sn,
                    key,
                    tkey,
                    "gen",
                    unit,
                    dc,
                    sc,
                )
            )
        # Generator voltage from vip[0]
        entities.append(
            SunSynkVipSensor(
                coordinator,
                plant_id,
                sn,
                "gen",
                0,
                "volt",
                "generator_voltage",
                UnitOfElectricPotential.VOLT,
                SensorDeviceClass.VOLTAGE,
            )
        )

    # --- PV input sensors ---
    if inv_data.get("input"):
        # Total PV power
        entities.append(
            SunSynkInverterSensor(
                coordinator,
                plant_id,
                sn,
                "pac",
                "pv_power",
                "input",
                UnitOfPower.KILO_WATT,
                SensorDeviceClass.POWER,
            )
        )
        entities.append(
            SunSynkInverterSensor(
                coordinator,
                plant_id,
                sn,
                "etoday",
                "pv_energy_today",
                "input",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL,
            )
        )
        entities.append(
            SunSynkInverterSensor(
                coordinator,
                plant_id,
                sn,
                "etotal",
                "pv_energy_total",
                "input",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL,
            )
        )
        # Per-string PV sensors
        input_obj = inv_data["input"]
        pv_iv: list[Any] = getattr(input_obj, "pv_iv", None) or []
        for idx in range(len(pv_iv)):
            entities.extend(
                [
                    SunSynkPvStringSensor(
                        coordinator,
                        plant_id,
                        sn,
                        idx,
                        "ppv",
                        "pv_string_power",
                        UnitOfPower.WATT,
                        SensorDeviceClass.POWER,
                    ),
                    SunSynkPvStringSensor(
                        coordinator,
                        plant_id,
                        sn,
                        idx,
                        "ipv",
                        "pv_string_current",
                        UnitOfElectricCurrent.AMPERE,
                        SensorDeviceClass.CURRENT,
                    ),
                    SunSynkPvStringSensor(
                        coordinator,
                        plant_id,
                        sn,
                        idx,
                        "vpv",
                        "pv_string_voltage",
                        UnitOfElectricPotential.VOLT,
                        SensorDeviceClass.VOLTAGE,
                    ),
                ]
            )

    # --- Inverter settings sensors (read-only mirrors, disabled by default) ---
    if inv_data.get("settings"):
        settings_defs: list[tuple[str, str]] = [
            ("sell_time1", "settings_sell_time_1"),
            ("sell_time2", "settings_sell_time_2"),
            ("sell_time3", "settings_sell_time_3"),
            ("sell_time4", "settings_sell_time_4"),
            ("sell_time5", "settings_sell_time_5"),
            ("sell_time6", "settings_sell_time_6"),
            ("cap1", "settings_soc_cap_1"),
            ("cap2", "settings_soc_cap_2"),
            ("cap3", "settings_soc_cap_3"),
            ("cap4", "settings_soc_cap_4"),
            ("cap5", "settings_soc_cap_5"),
            ("cap6", "settings_soc_cap_6"),
            ("time1on", "settings_timer_1_on"),
            ("time2on", "settings_timer_2_on"),
            ("time3on", "settings_timer_3_on"),
            ("time4on", "settings_timer_4_on"),
            ("time5on", "settings_timer_5_on"),
            ("time6on", "settings_timer_6_on"),
            ("gen_time1on", "settings_gen_timer_1_on"),
            ("gen_time2on", "settings_gen_timer_2_on"),
            ("gen_time3on", "settings_gen_timer_3_on"),
            ("gen_time4on", "settings_gen_timer_4_on"),
            ("gen_time5on", "settings_gen_timer_5_on"),
            ("gen_time6on", "settings_gen_timer_6_on"),
            ("peak_and_vallery", "settings_use_timer"),
            ("energy_mode", "settings_energy_mode"),
            ("sys_work_mode", "settings_sys_work_mode"),
            ("sell_time1_pac", "settings_sell_time_1_pac"),
            ("sell_time2_pac", "settings_sell_time_2_pac"),
            ("sell_time3_pac", "settings_sell_time_3_pac"),
            ("sell_time4_pac", "settings_sell_time_4_pac"),
            ("sell_time5_pac", "settings_sell_time_5_pac"),
            ("sell_time6_pac", "settings_sell_time_6_pac"),
            ("battery_restart_cap", "settings_battery_restart_cap"),
            ("battery_shutdown_cap", "settings_battery_shutdown_cap"),
            ("battery_max_current_charge", "settings_battery_max_charge_current"),
        ]
        for key, tkey in settings_defs:
            entities.append(
                SunSynkInverterSettingsSensor(
                    coordinator,
                    plant_id,
                    sn,
                    key,
                    tkey,
                    "settings",
                    None,
                    None,
                    None,
                )
            )

    # --- Temperature sensors ---
    if inv_data.get("temp"):
        entities.extend(
            [
                SunSynkInverterTempSensor(
                    coordinator,
                    plant_id,
                    sn,
                    "dc_temp",
                    "dc_temperature",
                    UnitOfTemperature.CELSIUS,
                    SensorDeviceClass.TEMPERATURE,
                ),
                SunSynkInverterTempSensor(
                    coordinator,
                    plant_id,
                    sn,
                    "igbt_temp",
                    "igbt_temperature",
                    UnitOfTemperature.CELSIUS,
                    SensorDeviceClass.TEMPERATURE,
                ),
            ]
        )

    # --- Computed sensors (Phase 2) ---
    entities.extend(_create_computed_sensors(coordinator, plant_id, sn, inv_data))

    return entities


# ---------------------------------------------------------------------------
# Compute helpers for derived sensors
# ---------------------------------------------------------------------------


def _compute_current_from_power(
    source_key: str,
    power_attr: str,
) -> Callable[[dict[str, Any]], float | None]:
    """Return a compute function that derives current from power / vip[0].volt."""

    def _compute(data: dict[str, Any]) -> float | None:
        source = data.get(source_key)
        if not source:
            return None
        power = safe_float(getattr(source, power_attr, None))
        vip = getattr(source, "vip", None)
        if not vip or len(vip) == 0:
            return None
        volt = safe_float(getattr(vip[0], "volt", None))
        if power is None or volt is None or volt == 0:
            return None
        return round(power * 1000 / volt, 2)

    return _compute


def _compute_sum_of_list_attr(
    source_key: str,
    list_attr: str,
    item_attr: str,
) -> Callable[[dict[str, Any]], float | None]:
    """Return a compute function that sums an attribute across a list."""

    def _compute(data: dict[str, Any]) -> float | None:
        source = data.get(source_key)
        if not source:
            return None
        items = getattr(source, list_attr, None)
        if not items:
            return None
        total = 0.0
        for item in items:
            val = safe_float(getattr(item, item_attr, None))
            if val is not None:
                total += val
        return round(total, 2)

    return _compute


def _compute_battery_efficiency(data: dict[str, Any]) -> float | None:
    """Compute battery efficiency: 100 - (chg - dischg) / dischg * 100."""
    batt = data.get("battery")
    if not batt:
        return None
    chg = safe_float(getattr(batt, "etotal_chg", None))
    dischg = safe_float(getattr(batt, "etotal_dischg", None))
    if chg is None or dischg is None or dischg == 0:
        return None
    return round(100 - (chg - dischg) / dischg * 100, 1)


def _compute_internal_power(data: dict[str, Any]) -> float | None:
    """Compute internal power: pv + grid + battery - load."""
    pv_power = safe_float(getattr(data.get("input"), "pac", None))
    grid_power = safe_float(getattr(data.get("grid"), "pac", None))
    batt_power = safe_float(getattr(data.get("battery"), "power", None))
    load_power = safe_float(getattr(data.get("load"), "total_power", None))
    if (
        pv_power is None
        or grid_power is None
        or batt_power is None
        or load_power is None
    ):
        return None
    return round(pv_power + grid_power + batt_power - load_power, 3)


# ---------------------------------------------------------------------------
# Factory: computed / derived sensors
# ---------------------------------------------------------------------------

# (source_key, unique_key, name, compute_fn, unit, device_class)
_COMPUTED_CURRENT_DEFS: list[
    tuple[
        str, str, str, Callable[[dict[str, Any]], float | None], str, SensorDeviceClass
    ]
] = [
    (
        "load",
        "load_current",
        "computed_load_current",
        _compute_current_from_power("load", "total_power"),
        UnitOfElectricCurrent.AMPERE,
        SensorDeviceClass.CURRENT,
    ),
    (
        "grid",
        "grid_current",
        "computed_grid_current",
        _compute_current_from_power("grid", "pac"),
        UnitOfElectricCurrent.AMPERE,
        SensorDeviceClass.CURRENT,
    ),
    (
        "input",
        "pv_total_current",
        "computed_pv_total_current",
        _compute_sum_of_list_attr("input", "pv_iv", "ipv"),
        UnitOfElectricCurrent.AMPERE,
        SensorDeviceClass.CURRENT,
    ),
    (
        "output",
        "output_total_current",
        "computed_output_total_current",
        _compute_sum_of_list_attr("output", "vip", "current"),
        UnitOfElectricCurrent.AMPERE,
        SensorDeviceClass.CURRENT,
    ),
    (
        "gen",
        "gen_total_current",
        "computed_gen_total_current",
        _compute_sum_of_list_attr("gen", "vip", "current"),
        UnitOfElectricCurrent.AMPERE,
        SensorDeviceClass.CURRENT,
    ),
]


def _create_computed_sensors(
    coordinator: SunSynkCoordinator,
    plant_id: int,
    sn: str,
    inv_data: dict[str, Any],
) -> list[SensorEntity]:
    """Create computed sensors that derive values from multiple data sources."""
    entities: list[SensorEntity] = []

    if inv_data.get("battery"):
        entities.append(
            SunSynkComputedSensor(
                coordinator,
                plant_id,
                sn,
                "battery_efficiency",
                "computed_battery_efficiency",
                _compute_battery_efficiency,
                PERCENTAGE,
                None,
            )
        )

    for source_key, unique_key, tkey, compute_fn, unit, dc in _COMPUTED_CURRENT_DEFS:
        if inv_data.get(source_key):
            entities.append(
                SunSynkComputedSensor(
                    coordinator,
                    plant_id,
                    sn,
                    unique_key,
                    tkey,
                    compute_fn,
                    unit,
                    dc,
                )
            )

    if all(inv_data.get(k) for k in ("input", "grid", "battery", "load")):
        entities.append(
            SunSynkComputedSensor(
                coordinator,
                plant_id,
                sn,
                "internal_power_usage",
                "computed_internal_power_usage",
                _compute_internal_power,
                UnitOfPower.KILO_WATT,
                SensorDeviceClass.POWER,
            )
        )

    # Raw data sensors (usable containers for template sensor compatibility)
    for source_type, raw_name in (
        ("grid", "SunSynk Usable Grid"),
        ("load", "SunSynk Usable Load"),
        ("output", "SunSynk Usable Inverter"),
    ):
        if inv_data.get(source_type):
            entities.append(
                SunSynkRawDataSensor(
                    coordinator,
                    plant_id,
                    sn,
                    source_type,
                    raw_name,
                )
            )

    return entities


# ---------------------------------------------------------------------------
# Factory: consolidated plant sensors (multi-inverter aggregation)
# ---------------------------------------------------------------------------


def _create_consolidated_sensors(
    coordinator: SunSynkCoordinator,
    plant_id: int,
    inverter_count: int,
) -> list[SensorEntity]:
    """Create consolidated sensors that sum across all inverters in a plant.

    Only created when a plant has more than one inverter.
    """
    if inverter_count <= 1:
        return []

    consol_defs: list[
        tuple[
            str, str, str, str | None, SensorDeviceClass | None, SensorStateClass | None
        ]
    ] = [
        (
            "input",
            "pac",
            "total_pv_power",
            UnitOfPower.KILO_WATT,
            SensorDeviceClass.POWER,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "load",
            "total_power",
            "total_load_power",
            UnitOfPower.KILO_WATT,
            SensorDeviceClass.POWER,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "battery",
            "power",
            "total_battery_power",
            UnitOfPower.KILO_WATT,
            SensorDeviceClass.POWER,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "battery",
            "current",
            "total_battery_current",
            UnitOfElectricCurrent.AMPERE,
            SensorDeviceClass.CURRENT,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "grid",
            "pac",
            "total_grid_power",
            UnitOfPower.KILO_WATT,
            SensorDeviceClass.POWER,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "output",
            "pac",
            "total_output_power",
            UnitOfPower.KILO_WATT,
            SensorDeviceClass.POWER,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "gen",
            "total_power",
            "total_generator_power",
            UnitOfPower.KILO_WATT,
            SensorDeviceClass.POWER,
            SensorStateClass.MEASUREMENT,
        ),
    ]
    return [
        SunSynkConsolidatedSensor(
            coordinator,
            plant_id,
            source,
            key,
            name,
            unit,
            dc,
            sc,
        )
        for source, key, name, unit, dc, sc in consol_defs
    ]


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SunSynkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SunSynk sensor platform."""
    coordinator = entry.runtime_data.coordinator

    if not coordinator.data:
        _LOGGER.warning("No data found in SunSynk")
        return

    entities: list[SensorEntity] = []

    # Gateway sensors
    entities.extend(
        _create_gateway_sensors(
            coordinator,
            coordinator.data.get("gateways", []),
        )
    )

    # Event sensors
    entities.extend(
        [
            SunSynkEventSensor(coordinator, 1, "info_events"),
            SunSynkEventSensor(coordinator, 2, "warning_events"),
            SunSynkEventSensor(coordinator, 3, "alarm_events"),
        ]
    )

    # Notification sensor
    entities.append(SunSynkNotificationSensor(coordinator))

    # Error tracking sensor
    entities.append(SunSynkErrorSensor(coordinator))

    # Last update timestamp sensor
    entities.append(SunSynkLastUpdateSensor(coordinator))

    # Plant, inverter, and consolidated sensors
    for plant_id, plant_data in coordinator.data.get("plants", {}).items():
        if plant_data.get("flow"):
            entities.extend(_create_plant_flow_sensors(coordinator, plant_id))

        inverters = plant_data.get("inverters", {})
        for sn, inv_data in inverters.items():
            entities.extend(
                _create_inverter_sensors(coordinator, plant_id, sn, inv_data)
            )

        # Multi-inverter consolidated sensors
        entities.extend(
            _create_consolidated_sensors(coordinator, plant_id, len(inverters))
        )

    async_add_entities(entities)
