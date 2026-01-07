"""Sensor platform for Qube Heat Pump."""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.loader import async_get_integration, async_get_loaded_integration
from homeassistant.util import dt as dt_util

from .const import DOMAIN, TARIFF_OPTIONS

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
    from homeassistant.helpers.typing import StateType

    from . import QubeConfigEntry
    from .hub import EntityDef, QubeHub

_LOGGER = logging.getLogger(__name__)

VENDOR_SLUG_OVERRIDES = {
    "unitstatus": "qube_status_heatpump",
}

HIDDEN_VENDOR_IDS = {
    "unitstatus",
    "dout_threewayvlv_val",
    "dout_fourwayvlv_val",
}

STANDBY_POWER_WATTS = 17.0
STANDBY_POWER_UNIQUE_BASE = "qube_standby_power"
STANDBY_ENERGY_UNIQUE_BASE = "qube_standby_energy"
TOTAL_ENERGY_UNIQUE_BASE = "qube_total_energy_with_standby"
BINARY_TARIFF_UNIQUE_ID = "dout_threewayvlv_val"
TARIFF_SENSOR_BASE = "qube_energy_tariff"
THERMIC_TARIFF_SENSOR_BASE = "qube_thermic_energy_tariff"
THERMIC_TOTAL_MONTHLY_UNIQUE_BASE = "qube_thermic_energy_monthly"
SCOP_TOTAL_UNIQUE_BASE = "qube_scop_monthly"
SCOP_CV_UNIQUE_BASE = "qube_scop_cv_monthly"
SCOP_SWW_UNIQUE_BASE = "qube_scop_sww_monthly"
SCOP_TOTAL_DAILY_UNIQUE_BASE = "qube_scop_daily"
SCOP_CV_DAILY_UNIQUE_BASE = "qube_scop_cv_daily"
SCOP_SWW_DAILY_UNIQUE_BASE = "qube_scop_sww_daily"
SCOP_MAX_EXPECTED = 10.0


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
    apply_label = data.apply_label_in_name
    multi_device = data.multi_device

    base_counts = {
        "sensor": sum(1 for e in hub.entities if e.platform == "sensor"),
        "binary_sensor": sum(1 for e in hub.entities if e.platform == "binary_sensor"),
        "switch": sum(1 for e in hub.entities if e.platform == "switch"),
    }

    extra_counts = {"sensor": 0, "binary_sensor": 0, "switch": 0}

    entities: list[SensorEntity] = []

    def _computed_object_base(name: str, use_prefix: bool) -> str:
        """Return the computed sensor object_id base."""
        slug = _slugify(name)
        if use_prefix:
            return slug
        if slug.startswith("qube_"):
            return slug[len("qube_") :]
        return slug

    def _add_sensor_entity(
        entity: SensorEntity, include_in_sensor_total: bool = True
    ) -> None:
        if include_in_sensor_total:
            extra_counts["sensor"] += 1
        entities.append(entity)

    # Use a container for counts to pass to sensors
    counts_holder: dict[str, dict[str, int] | None] = {"value": None}

    def _get_counts() -> dict[str, int] | None:
        return counts_holder["value"]

    # Surface the resolved host IP as its own diagnostic sensor
    _add_sensor_entity(
        QubeIPAddressSensor(coordinator, hub, apply_label, multi_device, version)
    )

    # Diagnostic metrics
    for kind in (
        "errors_connect",
        "errors_read",
        "count_sensors",
        "count_binary_sensors",
        "count_switches",
    ):
        include = not kind.startswith("count_") or kind == "count_sensors"
        if kind in ("count_sensors", "count_binary_sensors", "count_switches"):
            include = False
        _add_sensor_entity(
            QubeMetricSensor(
                coordinator,
                hub,
                apply_label,
                multi_device,
                version,
                kind=kind,
                counts_provider=_get_counts,
            ),
            include_in_sensor_total=include,
        )

    for ent in hub.entities:
        if ent.platform != "sensor":
            continue
        _add_sensor_entity(
            QubeSensor(
                coordinator,
                hub,
                apply_label,
                multi_device,
                version,
                ent,
            )
        )

    # 1) Qube status full
    status_src = _find_status_source(hub)
    if status_src is not None:
        _add_sensor_entity(
            QubeComputedSensor(
                coordinator,
                hub,
                translation_key="status_heatpump",
                unique_suffix="status_full",
                kind="status",
                source=status_src,
                show_label=apply_label,
                multi_device=multi_device,
                version=version,
                object_base=_computed_object_base("Status warmtepomp", apply_label),
            )
        )

    # 2) Qube Driewegklep (binary sensor 4)
    drie_src = _find_binary_by_address(hub, 4)
    if drie_src is not None:
        _add_sensor_entity(
            QubeComputedSensor(
                coordinator,
                hub,
                translation_key="drieweg_status",
                unique_suffix="driewegklep_dhw_cv",
                kind="drieweg",
                source=drie_src,
                show_label=apply_label,
                multi_device=multi_device,
                version=version,
                object_base=_computed_object_base(
                    "Qube Driewegklep SSW/CV status", apply_label
                ),
            )
        )

    # 3) Qube Vierwegklep (binary sensor 2)
    vier_src = _find_binary_by_address(hub, 2)
    if vier_src is not None:
        _add_sensor_entity(
            QubeComputedSensor(
                coordinator,
                hub,
                translation_key="vierweg_status",
                unique_suffix="vierwegklep_verwarmen_koelen",
                kind="vierweg",
                source=vier_src,
                show_label=apply_label,
                multi_device=multi_device,
                version=version,
                object_base=_computed_object_base(
                    "Qube Vierwegklep verwarmen/koelen status", apply_label
                ),
            )
        )

    standby_power = QubeStandbyPowerSensor(
        coordinator, hub, apply_label, multi_device, version
    )
    standby_energy = QubeStandbyEnergySensor(
        coordinator, hub, apply_label, multi_device, version
    )
    total_energy = QubeTotalEnergyIncludingStandbySensor(
        coordinator,
        hub,
        apply_label,
        multi_device,
        version,
        base_unique_id=_energy_unique_id(hub.label, multi_device),
        standby_sensor=standby_energy,
    )

    _add_sensor_entity(standby_power)
    _add_sensor_entity(standby_energy)
    _add_sensor_entity(total_energy)

    tracker = entry.runtime_data.tariff_tracker
    if tracker is None:
        tracker = TariffEnergyTracker(
            base_key=_energy_unique_id(hub.label, multi_device),
            binary_key=_binary_unique_id(hub.label, multi_device),
            tariffs=list(TARIFF_OPTIONS),
        )
        entry.runtime_data.tariff_tracker = tracker
    initial_data = coordinator.data or {}
    tracker.set_initial_total(initial_data.get(tracker.base_key))

    thermic_tracker = entry.runtime_data.thermic_tariff_tracker
    if thermic_tracker is None:
        thermic_tracker = TariffEnergyTracker(
            base_key=_thermic_energy_unique_id(hub.label, multi_device),
            binary_key=_binary_unique_id(hub.label, multi_device),
            tariffs=list(TARIFF_OPTIONS),
        )
        entry.runtime_data.thermic_tariff_tracker = thermic_tracker
    thermic_tracker.set_initial_total(initial_data.get(thermic_tracker.base_key))

    daily_electric_tracker = entry.runtime_data.daily_tariff_tracker
    if daily_electric_tracker is None:
        daily_electric_tracker = TariffEnergyTracker(
            base_key=_energy_unique_id(hub.label, multi_device),
            binary_key=_binary_unique_id(hub.label, multi_device),
            tariffs=list(TARIFF_OPTIONS),
            reset_period="day",
        )
        entry.runtime_data.daily_tariff_tracker = daily_electric_tracker
    daily_electric_tracker.set_initial_total(
        initial_data.get(daily_electric_tracker.base_key)
    )

    daily_thermic_tracker = entry.runtime_data.daily_thermic_tariff_tracker
    if daily_thermic_tracker is None:
        daily_thermic_tracker = TariffEnergyTracker(
            base_key=_thermic_energy_unique_id(hub.label, multi_device),
            binary_key=_binary_unique_id(hub.label, multi_device),
            tariffs=list(TARIFF_OPTIONS),
            reset_period="day",
        )
        entry.runtime_data.daily_thermic_tariff_tracker = daily_thermic_tracker
    daily_thermic_tracker.set_initial_total(
        initial_data.get(daily_thermic_tracker.base_key)
    )

    _add_sensor_entity(
        QubeTariffEnergySensor(
            coordinator,
            hub,
            tracker,
            tariff="CV",
            translation_key="electric_consumption_cv_month",
            show_label=apply_label,
            multi_device=multi_device,
            version=version,
        )
    )
    _add_sensor_entity(
        QubeTariffEnergySensor(
            coordinator,
            hub,
            tracker,
            tariff="SWW",
            translation_key="electric_consumption_sww_month",
            show_label=apply_label,
            multi_device=multi_device,
            version=version,
        )
    )
    _add_sensor_entity(
        QubeTariffTotalEnergySensor(
            coordinator,
            hub,
            thermic_tracker,
            translation_key="thermic_yield_month",
            show_label=apply_label,
            multi_device=multi_device,
            version=version,
            base_unique=THERMIC_TOTAL_MONTHLY_UNIQUE_BASE,
            object_base="thermische_opbrengst_maand",
        )
    )
    _add_sensor_entity(
        QubeTariffEnergySensor(
            coordinator,
            hub,
            thermic_tracker,
            tariff="CV",
            translation_key="thermic_yield_cv_month",
            show_label=apply_label,
            multi_device=multi_device,
            version=version,
            base_unique=THERMIC_TARIFF_SENSOR_BASE,
            object_base="thermische_opbrengst_cv_maand",
        )
    )
    _add_sensor_entity(
        QubeTariffEnergySensor(
            coordinator,
            hub,
            thermic_tracker,
            tariff="SWW",
            translation_key="thermic_yield_sww_month",
            show_label=apply_label,
            multi_device=multi_device,
            version=version,
            base_unique=THERMIC_TARIFF_SENSOR_BASE,
            object_base="thermische_opbrengst_sww_maand",
        )
    )

    _add_sensor_entity(
        QubeSCOPSensor(
            coordinator,
            hub,
            electric_tracker=tracker,
            thermic_tracker=thermic_tracker,
            scope="total",
            translation_key="scop_month",
            unique_base=SCOP_TOTAL_UNIQUE_BASE,
            object_base="scop_maand",
            show_label=apply_label,
            multi_device=multi_device,
            version=version,
        )
    )
    _add_sensor_entity(
        QubeSCOPSensor(
            coordinator,
            hub,
            electric_tracker=tracker,
            thermic_tracker=thermic_tracker,
            scope="CV",
            translation_key="scop_cv_month",
            unique_base=SCOP_CV_UNIQUE_BASE,
            object_base="scop_cv_maand",
            show_label=apply_label,
            multi_device=multi_device,
            version=version,
        )
    )
    _add_sensor_entity(
        QubeSCOPSensor(
            coordinator,
            hub,
            electric_tracker=tracker,
            thermic_tracker=thermic_tracker,
            scope="SWW",
            translation_key="scop_sww_month",
            unique_base=SCOP_SWW_UNIQUE_BASE,
            object_base="scop_sww_maand",
            show_label=apply_label,
            multi_device=multi_device,
            version=version,
        )
    )

    _add_sensor_entity(
        QubeSCOPSensor(
            coordinator,
            hub,
            electric_tracker=daily_electric_tracker,
            thermic_tracker=daily_thermic_tracker,
            scope="total",
            translation_key="scop_day",
            unique_base=SCOP_TOTAL_DAILY_UNIQUE_BASE,
            object_base="scop_dag",
            show_label=apply_label,
            multi_device=multi_device,
            version=version,
        )
    )
    _add_sensor_entity(
        QubeSCOPSensor(
            coordinator,
            hub,
            electric_tracker=daily_electric_tracker,
            thermic_tracker=daily_thermic_tracker,
            scope="CV",
            translation_key="scop_cv_day",
            unique_base=SCOP_CV_DAILY_UNIQUE_BASE,
            object_base="scop_cv_dag",
            show_label=apply_label,
            multi_device=multi_device,
            version=version,
        )
    )
    _add_sensor_entity(
        QubeSCOPSensor(
            coordinator,
            hub,
            electric_tracker=daily_electric_tracker,
            thermic_tracker=daily_thermic_tracker,
            scope="SWW",
            translation_key="scop_sww_day",
            unique_base=SCOP_SWW_DAILY_UNIQUE_BASE,
            object_base="scop_sww_dag",
            show_label=apply_label,
            multi_device=multi_device,
            version=version,
        )
    )

    info_sensor = QubeInfoSensor(
        coordinator,
        hub,
        apply_label,
        multi_device,
        version,
        total_counts=None,
    )
    _add_sensor_entity(info_sensor)

    final_counts = {
        "sensor": base_counts["sensor"] + extra_counts["sensor"],
        "binary_sensor": base_counts["binary_sensor"],
        "switch": base_counts["switch"],
    }

    info_sensor.set_counts(final_counts)
    counts_holder["value"] = final_counts

    async_add_entities(entities)


async def _async_ensure_entity_id(
    hass: HomeAssistant, entity_id: str, desired_obj: str | None
) -> None:
    """Ensure the entity_id aligns with the desired object id when possible."""
    if not desired_obj:
        return
    registry = er.async_get(hass)
    current = registry.async_get(entity_id)
    if not current:
        return
    desired_eid = f"{current.domain}.{desired_obj}"
    if current.entity_id == desired_eid:
        return
    if registry.async_get(desired_eid):
        return
    with contextlib.suppress(Exception):
        registry.async_update_entity(current.entity_id, new_entity_id=desired_eid)


class QubeSensor(CoordinatorEntity, SensorEntity):
    """Qube generic sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: Any,
        hub: QubeHub,
        show_label: bool,
        multi_device: bool,
        version: str,
        ent: EntityDef,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._ent = ent
        self._hub = hub
        self._host = hub.host
        self._unit = hub.unit
        self._label = hub.label
        self._show_label = bool(show_label)
        self._multi_device = bool(multi_device)
        self._version = version
        if ent.translation_key:
            manual_name = hub.get_friendly_name("sensor", ent.translation_key)
            if manual_name:
                self._attr_name = manual_name
                self._attr_has_entity_name = False
            else:
                self._attr_translation_key = ent.translation_key
                self._attr_has_entity_name = True
        else:
            self._attr_name = str(ent.name)
        if ent.unique_id:
            self._attr_unique_id = ent.unique_id
        else:
            suffix_parts = []
            if ent.input_type:
                suffix_parts.append(str(ent.input_type))
            if ent.write_type and not suffix_parts:
                suffix_parts.append(str(ent.write_type))
            suffix_parts.append(str(ent.address))
            suffix = "_".join(str(part) for part in suffix_parts if part)
            unique_base = f"qube_{ent.platform}_{suffix}".lower()
            if self._multi_device:
                unique_base = f"{unique_base}_{self._hub.entry_id}"
            self._attr_unique_id = unique_base
        vendor_id = getattr(ent, "vendor_id", None)
        if vendor_id in HIDDEN_VENDOR_IDS:
            self._attr_entity_registry_visible_default = False
            self._attr_entity_registry_enabled_default = False
        if vendor_id:
            vendor_slug = VENDOR_SLUG_OVERRIDES.get(vendor_id, vendor_id)
            desired = vendor_slug
            if self._show_label:
                desired = f"{self._label}_{desired}"
            self._attr_suggested_object_id = _slugify(desired)
        self._attr_device_class = cast("SensorDeviceClass | None", ent.device_class)
        self._attr_native_unit_of_measurement = ent.unit_of_measurement
        if ent.state_class:
            self._attr_state_class = ent.state_class
        # Hint UI display precision
        if ent.precision is not None:
            with contextlib.suppress(Exception):
                self._attr_suggested_display_precision = int(ent.precision)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._host}:{self._unit}")},
            name=(self._label or "Qube Heatpump"),
            manufacturer="Qube",
            model="Heatpump",
            sw_version=self._version,
        )

    @property
    def native_value(self) -> StateType:
        """Return native value."""
        key = (
            self._ent.unique_id
            or f"sensor_{self._ent.input_type or self._ent.write_type}_{self._ent.address}"
        )
        return self.coordinator.data.get(key)

    async def async_added_to_hass(self) -> None:
        """Handle entity addition."""
        await super().async_added_to_hass()
        desired = self._ent.vendor_id or self._attr_unique_id
        if (
            desired
            and self._show_label
            and not str(desired).startswith(f"{self._label}_")
        ):
            desired = f"{self._label}_{desired}"
        desired_slug = _slugify(str(desired)) if desired else None
        await _async_ensure_entity_id(self.hass, self.entity_id, desired_slug)


class QubeInfoSensor(CoordinatorEntity, SensorEntity):
    """Diagnostic info sensor."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: Any,
        hub: QubeHub,
        show_label: bool,
        multi_device: bool,
        version: str,
        total_counts: dict[str, int] | None = None,
    ) -> None:
        """Initialize info sensor."""
        super().__init__(coordinator)
        self._hub = hub
        self._multi_device = bool(multi_device)
        self._show_label = bool(show_label)
        self._version = str(version) if version else "unknown"
        self._total_counts = total_counts or {}
        label = hub.label or "qube1"
        self._attr_translation_key = "info"
        self._attr_has_entity_name = True
        self._attr_unique_id = (
            f"qube_info_sensor_{hub.entry_id}"
            if self._multi_device
            else "qube_info_sensor"
        )
        self._state = "ok"
        self._attr_suggested_object_id = "qube_info"
        if self._show_label:
            self._attr_suggested_object_id = _slugify(f"{label}_qube_info")

    def set_counts(self, counts: dict[str, int]) -> None:
        """Update total entity counts."""
        self._total_counts = counts

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._hub.host}:{self._hub.unit}")},
            name=(self._hub.label or "Qube Heatpump"),
            manufacturer="Qube",
            model="Heatpump",
            sw_version=self._version,
        )

    @property
    def native_value(self) -> str:
        """Return state."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attributes."""
        hub = self._hub
        counts = self._total_counts
        sensors = counts.get("sensor")
        bsens = counts.get("binary_sensor")
        switches = counts.get("switch")
        if sensors is None or bsens is None or switches is None:
            sensors = (
                sensors
                if sensors is not None
                else sum(1 for e in hub.entities if e.platform == "sensor")
            )
            bsens = (
                bsens
                if bsens is not None
                else sum(1 for e in hub.entities if e.platform == "binary_sensor")
            )
            switches = (
                switches
                if switches is not None
                else sum(1 for e in hub.entities if e.platform == "switch")
            )
        return {
            "version": self._version,
            "label": hub.label,
            "host": hub.host,
            "ip_address": hub.resolved_ip,
            "unit_id": hub.unit,
            "errors_connect": hub.err_connect,
            "errors_read": hub.err_read,
            "count_sensors": sensors,
            "count_binary_sensors": bsens,
            "count_switches": switches,
        }

    async def async_added_to_hass(self) -> None:
        """Handle entity addition."""
        await super().async_added_to_hass()
        desired_obj = self._attr_suggested_object_id or "qube_info"
        if self._show_label:
            desired_obj = _slugify(f"{self._hub.label}_qube_info")
        await _async_ensure_entity_id(self.hass, self.entity_id, desired_obj)
        # We could add version refresh logic here, but avoiding blind exceptions
        # requires careful handling. Simplified for now.
        with contextlib.suppress(Exception):
            await self._async_refresh_integration_version()

    async def _async_refresh_integration_version(self) -> None:
        """Refresh version info."""
        integ = None
        with contextlib.suppress(Exception):
            integ = async_get_loaded_integration(self.hass, DOMAIN)
        if not integ:
            with contextlib.suppress(Exception):
                integ = await async_get_integration(self.hass, DOMAIN)
        if integ and getattr(integ, "version", None):
            new_version = str(integ.version)
            if new_version and new_version != self._version:
                self._version = new_version
                self.async_write_ha_state()


class QubeIPAddressSensor(CoordinatorEntity, SensorEntity):
    """IP Address Sensor."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: Any,
        hub: QubeHub,
        show_label: bool,
        multi_device: bool,
        version: str,
    ) -> None:
        """Initialize IP sensor."""
        super().__init__(coordinator)
        self._hub = hub
        self._version = str(version) if version else "unknown"
        self._multi_device = bool(multi_device)
        self._show_label = bool(show_label)
        label = hub.label or "qube1"
        self._attr_translation_key = "ip_address"
        self._attr_has_entity_name = True
        base_uid = "qube_ip_address"
        self._attr_unique_id = (
            f"{base_uid}_{hub.entry_id}" if self._multi_device else base_uid
        )
        self._attr_suggested_object_id = base_uid
        if self._show_label:
            self._attr_suggested_object_id = _slugify(f"{label}_{base_uid}")
        if hasattr(SensorDeviceClass, "IP"):
            self._attr_device_class = SensorDeviceClass.IP
        else:
            self._attr_device_class = None
        self._attr_icon = "mdi:ip"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._hub.host}:{self._hub.unit}")},
            name=(self._hub.label or "Qube Heatpump"),
            manufacturer="Qube",
            model="Heatpump",
            sw_version=self._version,
        )

    @property
    def native_value(self) -> str | None:
        """Return IP address."""
        return self._hub.resolved_ip or self._hub.host

    async def async_added_to_hass(self) -> None:
        """Handle entity addition."""
        await super().async_added_to_hass()
        desired_obj = self._attr_suggested_object_id or "qube_ip_address"
        if self._show_label:
            desired_obj = _slugify(f"{self._hub.label}_qube_ip_address")
        await _async_ensure_entity_id(self.hass, self.entity_id, desired_obj)


class QubeMetricSensor(CoordinatorEntity, SensorEntity):
    """Metric sensor."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: Any,
        hub: QubeHub,
        show_label: bool,
        multi_device: bool,
        version: str,
        kind: str,
        counts_provider: Callable[[], dict[str, int] | None] | None = None,
    ) -> None:
        """Initialize metric sensor."""
        super().__init__(coordinator)
        self._hub = hub
        self._kind = kind
        self._multi_device = bool(multi_device)
        self._show_label = bool(show_label)
        self._version = version
        self._counts_provider = counts_provider
        label = hub.label or "qube1"
        self._attr_translation_key = f"metric_{kind}"
        self._attr_has_entity_name = True
        base_uid = f"qube_metric_{kind}"
        self._attr_unique_id = (
            f"{base_uid}_{hub.entry_id}" if self._multi_device else base_uid
        )
        self._attr_suggested_object_id = _slugify(base_uid)
        if self._show_label:
            self._attr_suggested_object_id = _slugify(f"{label}_{base_uid}")
        with contextlib.suppress(Exception):
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._hub.host}:{self._hub.unit}")},
            name=(self._hub.label or "Qube Heatpump"),
            manufacturer="Qube",
            model="Heatpump",
            sw_version=self._version,
        )

    @property
    def native_value(self) -> int | None:
        """Return native value."""
        hub = self._hub
        if self._kind == "errors_connect":
            return getattr(hub, "err_connect", None)
        if self._kind == "errors_read":
            return getattr(hub, "err_read", None)
        if self._kind == "count_sensors":
            counts = self._counts_provider() if self._counts_provider else None
            if counts:
                return counts.get("sensor", 0)
            return sum(1 for e in hub.entities if e.platform == "sensor")
        if self._kind == "count_binary_sensors":
            counts = self._counts_provider() if self._counts_provider else None
            if counts:
                return counts.get("binary_sensor", 0)
            return sum(1 for e in hub.entities if e.platform == "binary_sensor")
        if self._kind == "count_switches":
            counts = self._counts_provider() if self._counts_provider else None
            if counts:
                return counts.get("switch", 0)
            return sum(1 for e in hub.entities if e.platform == "switch")
        return None

    async def async_added_to_hass(self) -> None:
        """Handle entity addition."""
        await super().async_added_to_hass()
        desired_obj = self._attr_suggested_object_id or _slugify(
            f"qube_metric_{self._kind}"
        )
        await _async_ensure_entity_id(self.hass, self.entity_id, desired_obj)


def _entity_key(ent: EntityDef) -> str:
    """Generate entity key."""
    return (
        ent.unique_id
        or f"{ent.platform}_{ent.input_type or ent.write_type}_{ent.address}"
    )


def _slugify(text: str) -> str:
    """Make text safe for use as an ID."""
    return "".join(ch if ch.isalnum() else "_" for ch in text).strip("_").lower()


def _find_status_source(hub: QubeHub) -> EntityDef | None:
    """Find status source entity."""
    for ent in hub.entities:
        if ent.platform == "sensor" and (
            ent.unique_id == "wp_qube_warmtepomp_unit_status"
        ):
            return ent
    cand: EntityDef | None = None
    for ent in hub.entities:
        if ent.platform != "sensor":
            continue
        if (ent.device_class == "enum") or ("status" in (ent.name or "").lower()):
            cand = ent
            break
    return cand


def _find_binary_by_address(hub: QubeHub, address: int) -> EntityDef | None:
    """Find binary sensor by address."""
    for ent in hub.entities:
        if ent.platform == "binary_sensor" and int(ent.address) == int(address):
            return ent
    return None


def _append_label(base: str, label: str | None, multi_device: bool) -> str:
    """Append label if needed."""
    if multi_device and label:
        return f"{base}_{label}"
    return base


def _energy_unique_id(label: str | None, multi_device: bool) -> str:
    """Generate energy unique ID."""
    base = "generalmng_acumulatedpwr"
    return _append_label(base, label, multi_device)


class QubeStandbyPowerSensor(CoordinatorEntity, SensorEntity):
    """Standby power sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: Any,
        hub: QubeHub,
        show_label: bool,
        multi_device: bool,
        version: str,
    ) -> None:
        """Initialize standby power sensor."""
        super().__init__(coordinator)
        self._hub = hub
        self._label = hub.label or "qube1"
        self._multi_device = bool(multi_device)
        self._show_label = bool(show_label)
        self._version = version
        self._attr_translation_key = "standby_power"
        self._attr_has_entity_name = True
        unique = _append_label(STANDBY_POWER_UNIQUE_BASE, hub.entry_id, multi_device)
        self._attr_unique_id = unique
        suggested = STANDBY_POWER_UNIQUE_BASE
        if self._show_label:
            suggested = f"{self._label}_{suggested}"
        self._attr_suggested_object_id = suggested
        self._attr_device_class = SensorDeviceClass.POWER
        with contextlib.suppress(ValueError, TypeError):
            self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "W"
        self._attr_native_value = STANDBY_POWER_WATTS

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._hub.host}:{self._hub.unit}")},
            name=self._hub.label or "Qube Heatpump",
            manufacturer="Qube",
            model="Heatpump",
            sw_version=self._version,
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity addition."""
        await super().async_added_to_hass()
        desired_obj = self._attr_suggested_object_id or STANDBY_POWER_UNIQUE_BASE
        await _async_ensure_entity_id(
            self.hass, self.entity_id, _slugify(str(desired_obj))
        )


class QubeStandbyEnergySensor(CoordinatorEntity, RestoreSensor, SensorEntity):
    """Standby energy sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: Any,
        hub: QubeHub,
        show_label: bool,
        multi_device: bool,
        version: str,
    ) -> None:
        """Initialize standby energy sensor."""
        super().__init__(coordinator)
        self._hub = hub
        self._label = hub.label or "qube1"
        self._multi_device = bool(multi_device)
        self._show_label = bool(show_label)
        self._version = version
        self._energy_kwh: float = 0.0
        self._last_update: datetime | None = None
        self._attr_translation_key = "standby_energy"
        self._attr_has_entity_name = True
        unique = _append_label(STANDBY_ENERGY_UNIQUE_BASE, hub.entry_id, multi_device)
        self._attr_unique_id = unique
        suggested = STANDBY_ENERGY_UNIQUE_BASE
        if self._show_label:
            suggested = f"{self._label}_{suggested}"
        self._attr_suggested_object_id = suggested
        self._attr_device_class = SensorDeviceClass.ENERGY
        with contextlib.suppress(ValueError, TypeError):
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = "kWh"

    async def async_added_to_hass(self) -> None:
        """Handle entity addition."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "", "unknown", "unavailable"):
            try:
                self._energy_kwh = float(last_state.state)
            except (TypeError, ValueError):
                self._energy_kwh = 0.0
            self._last_update = last_state.last_changed
        if self._last_update is None:
            self._last_update = dt_util.utcnow()
        desired_obj = self._attr_suggested_object_id or STANDBY_ENERGY_UNIQUE_BASE
        await _async_ensure_entity_id(
            self.hass, self.entity_id, _slugify(str(desired_obj))
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._hub.host}:{self._hub.unit}")},
            name=self._hub.label or "Qube Heatpump",
            manufacturer="Qube",
            model="Heatpump",
            sw_version=self._version,
        )

    @property
    def native_value(self) -> float:
        """Return value."""
        return round(self._energy_kwh, 3)

    def _integrate(self) -> None:
        now = dt_util.utcnow()
        if self._last_update is None:
            self._last_update = now
            return
        elapsed = (now - self._last_update).total_seconds()
        if elapsed <= 0:
            return
        self._last_update = now
        delta_kwh = (STANDBY_POWER_WATTS / 1000.0) * (elapsed / 3600.0)
        self._energy_kwh += delta_kwh

    def _handle_coordinator_update(self) -> None:
        self._integrate()
        super()._handle_coordinator_update()

    def current_energy(self) -> float:
        """Return current energy."""
        self._integrate()
        return self._energy_kwh


class QubeTotalEnergyIncludingStandbySensor(CoordinatorEntity, SensorEntity):
    """Total energy sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: Any,
        hub: QubeHub,
        show_label: bool,
        multi_device: bool,
        version: str,
        base_unique_id: str,
        standby_sensor: QubeStandbyEnergySensor,
    ) -> None:
        """Initialize total energy sensor."""
        super().__init__(coordinator)
        self._hub = hub
        self._label = hub.label or "qube1"
        self._multi_device = bool(multi_device)
        self._show_label = bool(show_label)
        self._version = version
        self._base_unique_id = base_unique_id
        self._standby_sensor = standby_sensor
        self._total_energy: float | None = None
        self._attr_translation_key = "total_energy_incl_standby"
        self._attr_has_entity_name = True
        unique = _append_label(TOTAL_ENERGY_UNIQUE_BASE, hub.entry_id, multi_device)
        self._attr_unique_id = unique
        suggested = TOTAL_ENERGY_UNIQUE_BASE
        if self._show_label:
            suggested = f"{self._label}_{suggested}"
        self._attr_suggested_object_id = suggested
        self._attr_device_class = SensorDeviceClass.ENERGY
        with contextlib.suppress(ValueError, TypeError):
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = "kWh"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._hub.host}:{self._hub.unit}")},
            name=self._hub.label or "Qube Heatpump",
            manufacturer="Qube",
            model="Heatpump",
            sw_version=self._version,
        )

    @property
    def native_value(self) -> float | None:
        """Return value."""
        return None if self._total_energy is None else round(self._total_energy, 3)

    async def async_added_to_hass(self) -> None:
        """Handle entity addition."""
        await super().async_added_to_hass()
        desired_obj = self._attr_suggested_object_id or TOTAL_ENERGY_UNIQUE_BASE
        await _async_ensure_entity_id(
            self.hass, self.entity_id, _slugify(str(desired_obj))
        )

    def _handle_coordinator_update(self) -> None:
        base_value = self.coordinator.data.get(self._base_unique_id)
        standby = self._standby_sensor.current_energy()
        try:
            base_float = float(base_value) if base_value is not None else None
        except (TypeError, ValueError):
            base_float = None
        if base_float is None:
            self._total_energy = None
        else:
            self._total_energy = base_float + standby
        super()._handle_coordinator_update()


class QubeComputedSensor(CoordinatorEntity, SensorEntity):
    """Computed status sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: Any,
        hub: QubeHub,
        translation_key: str,
        unique_suffix: str,
        kind: str,
        source: EntityDef,
        show_label: bool,
        multi_device: bool,
        version: str,
        object_base: str | None = None,
    ) -> None:
        """Initialize computed sensor."""
        super().__init__(coordinator)
        self._hub = hub
        self._kind = kind
        self._source = source
        self._version = version
        self._multi_device = bool(multi_device)
        self._show_label = bool(show_label)
        self._label = hub.label or "qube1"
        self._object_base = _slugify(object_base) if object_base else _slugify(kind)
        self._attr_translation_key = translation_key
        self._attr_has_entity_name = True
        base_unique = f"qube_{unique_suffix}"
        self._attr_unique_id = (
            f"{base_unique}_{self._hub.entry_id}" if self._multi_device else base_unique
        )
        self._attr_suggested_object_id = self._object_base
        if self._show_label:
            self._attr_suggested_object_id = f"{self._label}_{self._object_base}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._hub.host}:{self._hub.unit}")},
            name=(self._hub.label or "Qube Heatpump"),
            manufacturer="Qube",
            model="Heatpump",
            sw_version=self._version,
        )

    @property
    def native_value(self) -> str | None:
        """Return native value."""
        key = _entity_key(self._source)
        val = self.coordinator.data.get(key)
        if val is None:
            return None
        with contextlib.suppress(Exception):
            if self._kind == "status":
                code = int(val)
                if code in (1, 14, 18):
                    return "standby"
                mapping = {
                    2: "alarm",
                    6: "keyboard_off",
                    8: "compressor_startup",
                    9: "compressor_shutdown",
                    15: "cooling",
                    16: "heating",
                    17: "start_fail",
                    22: "heating_dhw",
                }
                return mapping.get(code, "unknown")
            if self._kind == "drieweg":
                # DHW (True) vs CV (False)
                return "dhw" if bool(val) else "cv"
            if self._kind == "vierweg":
                # Verwarmen (True) vs Koelen (False) -> heating/cooling
                return "heating" if bool(val) else "cooling"
        return None

    async def async_added_to_hass(self) -> None:
        """Handle entity addition."""
        await super().async_added_to_hass()
        if self._show_label:
            desired = f"{self._label}_{self._object_base}"
        else:
            desired = self._object_base
        await _async_ensure_entity_id(self.hass, self.entity_id, _slugify(str(desired)))


def _start_of_month(dt_value: datetime) -> datetime:
    return dt_value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _start_of_day(dt_value: datetime) -> datetime:
    return dt_value.replace(hour=0, minute=0, second=0, microsecond=0)


def _thermic_energy_unique_id(label: str | None, multi_device: bool) -> str:
    base = "generalmng_acumulatedthermic"
    return _append_label(base, label, multi_device)


def _binary_unique_id(label: str | None, multi_device: bool) -> str:
    return _append_label(BINARY_TARIFF_UNIQUE_ID, label, multi_device)


class TariffEnergyTracker:
    """Track split energy totals for CV/SWW."""

    def __init__(
        self,
        base_key: str,
        binary_key: str,
        tariffs: list[str],
        reset_period: str = "month",
    ) -> None:
        """Initialize tracker."""
        self.base_key = base_key
        self.binary_key = binary_key
        self.tariffs = list(tariffs)
        self._totals: dict[str, float] = dict.fromkeys(tariffs, 0.0)
        self._current_tariff: str = tariffs[0]
        self._last_total: float | None = None
        self._reset_period = reset_period
        self._last_reset: datetime = self._cycle_start(dt_util.utcnow())
        self._last_token: datetime | None = None

    @property
    def current_tariff(self) -> str:
        """Return current tariff."""
        return self._current_tariff

    @property
    def last_reset(self) -> datetime:
        """Return last reset time."""
        return self._last_reset

    def restore_total(
        self, tariff: str, value: float, last_reset: datetime | None
    ) -> None:
        """Restore total from previous state."""
        if tariff in self._totals:
            self._totals[tariff] = max(0.0, value)
        if last_reset and last_reset > self._last_reset:
            self._last_reset = last_reset

    def set_initial_total(self, total: float | None) -> None:
        """Set initial total."""
        if total is None:
            return
        try:
            self._last_total = float(total)
        except (TypeError, ValueError):
            self._last_total = None

    def _cycle_start(self, dt_value: datetime) -> datetime:
        if self._reset_period == "day":
            return _start_of_day(dt_value)
        return _start_of_month(dt_value)

    def _reset_if_needed(self, reference: datetime | None) -> None:
        now = reference or dt_util.utcnow()
        start = self._cycle_start(now)
        if start > self._last_reset:
            self._last_reset = start
            for tariff in self._totals:
                self._totals[tariff] = 0.0

    def update(self, coordinator_data: dict[str, Any], token: datetime | None) -> None:
        """Update tracker with new data."""
        if (
            token is not None
            and self._last_token is not None
            and token <= self._last_token
        ):
            self._refresh_current_tariff(coordinator_data)
            return

        if token is not None:
            self._last_token = token

        base_val = coordinator_data.get(self.base_key)
        try:
            base_float = float(base_val) if base_val is not None else None
        except (TypeError, ValueError):
            base_float = None

        self._refresh_current_tariff(coordinator_data)

        if base_float is None:
            return

        if self._last_total is None:
            self._last_total = base_float
            return

        delta = base_float - self._last_total
        self._last_total = base_float
        if delta <= 0:
            return

        reference = token or dt_util.utcnow()
        self._reset_if_needed(reference)
        self._totals[self._current_tariff] += delta

    def _refresh_current_tariff(self, coordinator_data: dict[str, Any]) -> None:
        state = coordinator_data.get(self.binary_key)
        if isinstance(state, bool):
            self._current_tariff = "SWW" if state else "CV"

    def get_total(self, tariff: str) -> float:
        """Get total for tariff."""
        return self._totals.get(tariff, 0.0)


class QubeTariffEnergySensor(CoordinatorEntity, RestoreSensor, SensorEntity):
    """Tariff energy sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: Any,
        hub: QubeHub,
        tracker: TariffEnergyTracker,
        tariff: str,
        translation_key: str,
        show_label: bool,
        multi_device: bool,
        version: str,
        base_unique: str | None = None,
        object_base: str | None = None,
    ) -> None:
        """Initialize tariff sensor."""
        super().__init__(coordinator)
        self._hub = hub
        self._tracker = tracker
        self._tariff = tariff
        self._label = hub.label or "qube1"
        self._show_label = bool(show_label)
        self._multi_device = bool(multi_device)
        self._version = version
        self._attr_translation_key = translation_key
        self._attr_has_entity_name = True
        base_uid = f"{(base_unique or TARIFF_SENSOR_BASE)}_{tariff.lower()}"
        self._attr_unique_id = _append_label(base_uid, hub.entry_id, multi_device)
        suggested_base = object_base or base_uid
        suggested = suggested_base
        if self._show_label:
            suggested = f"{self._label}_{suggested}"
        self._attr_suggested_object_id = suggested
        self._attr_device_class = SensorDeviceClass.ENERGY
        with contextlib.suppress(ValueError, TypeError):
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = "kWh"

    async def async_added_to_hass(self) -> None:
        """Handle entity addition."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "", "unknown", "unavailable"):
            try:
                value = float(last_state.state)
            except (TypeError, ValueError):
                value = 0.0
            last_reset: datetime | None = None
            if hasattr(last_state, "last_reset"):
                last_reset = last_state.last_reset
            if not last_reset:
                cycle_start = (
                    last_state.attributes.get("cycle_start")
                    if last_state.attributes
                    else None
                )
                if cycle_start:
                    parsed = dt_util.parse_datetime(str(cycle_start))
                    if parsed is not None:
                        last_reset = parsed
            self._tracker.restore_total(self._tariff, value, last_reset)
        desired_obj = self._attr_suggested_object_id
        if desired_obj:
            await _async_ensure_entity_id(
                self.hass, self.entity_id, _slugify(str(desired_obj))
            )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._hub.host}:{self._hub.unit}")},
            name=self._hub.label or "Qube Heatpump",
            manufacturer="Qube",
            model="Heatpump",
            sw_version=self._version,
        )

    @property
    def native_value(self) -> float:
        """Return value."""
        return round(self._tracker.get_total(self._tariff), 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attributes."""
        return {"cycle_start": self._tracker.last_reset.isoformat()}

    def _handle_coordinator_update(self) -> None:
        token = getattr(self.coordinator, "last_update_success_time", None)
        data = self.coordinator.data or {}
        self._tracker.update(data, token)
        super()._handle_coordinator_update()


class QubeTariffTotalEnergySensor(CoordinatorEntity, SensorEntity):
    """Tariff total sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: Any,
        hub: QubeHub,
        tracker: TariffEnergyTracker,
        translation_key: str,
        show_label: bool,
        multi_device: bool,
        version: str,
        base_unique: str,
        object_base: str,
    ) -> None:
        """Initialize total sensor."""
        super().__init__(coordinator)
        self._hub = hub
        self._tracker = tracker
        self._label = hub.label or "qube1"
        self._show_label = bool(show_label)
        self._multi_device = bool(multi_device)
        self._version = version
        self._attr_translation_key = translation_key
        self._attr_has_entity_name = True
        self._attr_unique_id = _append_label(base_unique, hub.entry_id, multi_device)
        suggested = object_base
        if self._show_label:
            suggested = f"{self._label}_{suggested}"
        self._attr_suggested_object_id = suggested
        self._attr_device_class = SensorDeviceClass.ENERGY
        with contextlib.suppress(ValueError, TypeError):
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = "kWh"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._hub.host}:{self._hub.unit}")},
            name=self._hub.label or "Qube Heatpump",
            manufacturer="Qube",
            model="Heatpump",
            sw_version=self._version,
        )

    @property
    def native_value(self) -> float:
        """Return value."""
        return round(sum(self._tracker.get_total(t) for t in self._tracker.tariffs), 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attributes."""
        return {"cycle_start": self._tracker.last_reset.isoformat()}

    def _handle_coordinator_update(self) -> None:
        token = getattr(self.coordinator, "last_update_success_time", None)
        data = self.coordinator.data or {}
        self._tracker.update(data, token)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """Handle entity addition."""
        await super().async_added_to_hass()
        desired_obj = self._attr_suggested_object_id or self._attr_unique_id
        await _async_ensure_entity_id(
            self.hass, self.entity_id, _slugify(str(desired_obj))
        )


class QubeSCOPSensor(CoordinatorEntity, SensorEntity):
    """SCOP sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: Any,
        hub: QubeHub,
        electric_tracker: TariffEnergyTracker,
        thermic_tracker: TariffEnergyTracker,
        scope: str,
        translation_key: str,
        unique_base: str,
        object_base: str,
        show_label: bool,
        multi_device: bool,
        version: str,
    ) -> None:
        """Initialize SCOP sensor."""
        super().__init__(coordinator)
        self._hub = hub
        self._electric = electric_tracker
        self._thermic = thermic_tracker
        self._scope = scope
        self._label = hub.label or "qube1"
        self._show_label = bool(show_label)
        self._multi_device = bool(multi_device)
        self._version = version
        self._attr_translation_key = translation_key
        self._attr_has_entity_name = True
        self._object_base = object_base
        base_uid = unique_base
        if multi_device:
            base_uid = f"{base_uid}_{self._hub.entry_id}"
        self._attr_unique_id = base_uid
        suggested = object_base
        if self._show_label:
            suggested = f"{self._label}_{suggested}"
        self._attr_suggested_object_id = suggested
        self._attr_suggested_display_precision = 1
        self._attr_native_unit_of_measurement = "CoP"
        with contextlib.suppress(Exception):
            self._attr_state_class = SensorStateClass.TOTAL

    async def async_added_to_hass(self) -> None:
        """Handle entity addition."""
        await super().async_added_to_hass()
        desired = self._object_base
        if self._show_label:
            desired = f"{desired}_{self._label}"
        await _async_ensure_entity_id(self.hass, self.entity_id, _slugify(str(desired)))

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._hub.host}:{self._hub.unit}")},
            name=self._hub.label or "Qube Heatpump",
            manufacturer="Qube",
            model="Heatpump",
            sw_version=self._version,
        )

    def _current_totals(self) -> tuple[float | None, float | None]:
        if self._scope == "total":
            elec = sum(self._electric.get_total(t) for t in self._electric.tariffs)
            therm = sum(self._thermic.get_total(t) for t in self._thermic.tariffs)
            return elec, therm
        elec = self._electric.get_total(self._scope)
        therm = self._thermic.get_total(self._scope)
        return elec, therm

    @property
    def native_value(self) -> float | None:
        """Return value."""
        elec, therm = self._current_totals()
        if elec is None or therm is None:
            return None
        try:
            elec_f = float(elec)
            therm_f = float(therm)
        except (TypeError, ValueError):
            return None
        if elec_f <= 0:
            return None
        scop = therm_f / elec_f
        if scop < 0 or scop > SCOP_MAX_EXPECTED:
            return None
        return round(scop, 1)

    def _handle_coordinator_update(self) -> None:
        token = getattr(self.coordinator, "last_update_success_time", None)
        data = self.coordinator.data or {}
        self._electric.update(data, token)
        self._thermic.update(data, token)
        super()._handle_coordinator_update()
