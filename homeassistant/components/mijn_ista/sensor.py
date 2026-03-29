"""Sensor platform for mijn.ista.nl."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MANUFACTURER, SERVICE_NAME_TRANSLATIONS
from .coordinator import CustomerData, MijnIstaCoordinator

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

# Map API unit strings → HA unit constants
_UNIT_MAP: dict[str, str] = {
    "Gigajoule": UnitOfEnergy.GIGA_JOULE,
    "kWh": UnitOfEnergy.KILO_WATT_HOUR,
    "m3": UnitOfVolume.CUBIC_METERS,
    "m³": UnitOfVolume.CUBIC_METERS,
}

# Map API unit strings → HA SensorDeviceClass
_DEVICE_CLASS_MAP: dict[str, SensorDeviceClass | None] = {
    "Gigajoule": SensorDeviceClass.ENERGY,
    "kWh": SensorDeviceClass.ENERGY,
    "m3": SensorDeviceClass.WATER,
    "m³": SensorDeviceClass.WATER,
}


def _translate_service(description: str, ha_language: str) -> str:
    """Return English service name when HA language is English, otherwise pass through."""
    if ha_language.startswith("en"):
        return SERVICE_NAME_TRANSLATIONS.get(description, description)
    return description


def _ha_unit(api_unit: str) -> str | None:
    return _UNIT_MAP.get(api_unit)


def _ha_device_class(api_unit: str) -> SensorDeviceClass | None:
    return _DEVICE_CLASS_MAP.get(api_unit)


def _parse_dt(date_str: str) -> datetime | None:
    """Parse an API ISO date string to a UTC-aware datetime, or None."""
    if not date_str:
        return None
    dt = dt_util.parse_datetime(date_str)
    return dt_util.as_utc(dt) if dt else None


def _find_month(
    monthly: list, service_id: int
):
    """Return the most recent MonthEntry that has data for service_id."""
    return next((me for me in monthly if service_id in me.services), None)


class MijnIstaSensor(CoordinatorEntity, SensorEntity):
    """A single mijn.ista.nl sensor backed by MijnIstaCoordinator."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MijnIstaCoordinator,
        cuid: str,
        unique_id_suffix: str,
        name: str,
        unit: str | None,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
        value_fn: Callable[[CustomerData], Any],
        attrs_fn: Callable[[CustomerData], dict[str, Any]] | None = None,
        last_reset_fn: Callable[[CustomerData], datetime | None] | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._cuid = cuid
        self._value_fn = value_fn
        self._attrs_fn = attrs_fn
        self._last_reset_fn = last_reset_fn
        self._attr_unique_id = f"{DOMAIN}_{cuid}_{unique_id_suffix}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    @property
    def device_info(self) -> DeviceInfo:
        data: CustomerData | None = (
            self.coordinator.data.get(self._cuid) if self.coordinator.data else None
        )
        # Address goes in model so it's visible in the device panel but
        # never lands in entity IDs (which are derived from device name).
        model = (
            f"{data.address}, {data.zip_code} {data.city}" if data else self._cuid[:8]
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self._cuid)},
            name="ista NL",
            manufacturer=MANUFACTURER,
            model=model,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://mijn.ista.nl",
        )

    @property
    def native_value(self) -> Any:
        if not self.coordinator.data:
            return None
        customer = self.coordinator.data.get(self._cuid)
        if customer is None:
            return None
        try:
            return self._value_fn(customer)
        except (KeyError, IndexError, TypeError, AttributeError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data or self._attrs_fn is None:
            return {}
        customer = self.coordinator.data.get(self._cuid)
        if customer is None:
            return {}
        try:
            return self._attrs_fn(customer)
        except (KeyError, IndexError, TypeError, AttributeError):
            return {}

    @property
    def last_reset(self) -> datetime | None:
        """Return the time when the sensor was last reset, for TOTAL state class sensors."""
        if self._last_reset_fn is None:
            return None
        if not self.coordinator.data:
            return None
        customer = self.coordinator.data.get(self._cuid)
        if customer is None:
            return None
        try:
            return self._last_reset_fn(customer)
        except (KeyError, IndexError, TypeError, AttributeError, ValueError):
            return None


# ── sensor factory ──────────────────────────────────────────────────────────


def _build_sensors(
    coordinator: MijnIstaCoordinator,
    cuid: str,
    customer: CustomerData,
) -> list[MijnIstaSensor]:
    """Build the complete sensor list for one property (Cuid)."""
    sensors: list[MijnIstaSensor] = []
    svc_by_id = {s.id: s for s in customer.services}
    ha_lang = coordinator.hass.config.language

    # ── annual sensors (per service) ────────────────────────────────────────
    for sid, annual in customer.annual.items():
        svc = svc_by_id.get(sid)
        unit = _ha_unit(svc.unit) if svc else None
        dc = _ha_device_class(svc.unit) if svc else None
        label = (
            _translate_service(svc.description, ha_lang) if svc else f"Service {sid}"
        )

        # Current-year total
        sensors.append(
            MijnIstaSensor(
                coordinator,
                cuid,
                f"svc{sid}_annual_current",
                f"{label} Current",
                unit,
                dc,
                SensorStateClass.TOTAL,
                value_fn=lambda c, s=sid: c.annual[s].total_now
                if s in c.annual
                else None,
                attrs_fn=lambda c, s=sid: {
                    "period_start": c.annual[s].cur_meters[0].begin_date
                    if c.annual[s].cur_meters
                    else None,
                    "period_end": c.annual[s].cur_meters[0].end_date
                    if c.annual[s].cur_meters
                    else None,
                    "meters": [m.as_dict() for m in c.annual[s].cur_meters],
                }
                if s in c.annual
                else {},
                last_reset_fn=lambda c, s=sid: _parse_dt(
                    c.annual[s].cur_meters[0].begin_date
                )
                if s in c.annual and c.annual[s].cur_meters
                else None,
            )
        )

        # Previous-year total
        sensors.append(
            MijnIstaSensor(
                coordinator,
                cuid,
                f"svc{sid}_annual_previous",
                f"{label} Previous",
                unit,
                dc,
                SensorStateClass.TOTAL,
                value_fn=lambda c, s=sid: c.annual[s].total_previous
                if s in c.annual
                else None,
                attrs_fn=lambda c, s=sid: {
                    "total_whole_year": c.annual[s].total_whole_previous,
                    "meters": [m.as_dict() for m in c.annual[s].comp_meters],
                }
                if s in c.annual
                else {},
                last_reset_fn=lambda c, s=sid: _parse_dt(
                    c.annual[s].comp_meters[0].begin_date
                )
                if s in c.annual and c.annual[s].comp_meters
                else None,
            )
        )

        # Year-over-year change %
        sensors.append(
            MijnIstaSensor(
                coordinator,
                cuid,
                f"svc{sid}_annual_diff_pct",
                f"{label} Change",
                PERCENTAGE,
                None,
                SensorStateClass.MEASUREMENT,
                value_fn=lambda c, s=sid: c.annual[s].diff_pct
                if s in c.annual
                else None,
            )
        )

        # Annual building average (from ConsumptionAverages)
        if sid in customer.building_averages:
            sensors.append(
                MijnIstaSensor(
                    coordinator,
                    cuid,
                    f"svc{sid}_building_avg_annual",
                    f"{label} Building Avg",
                    unit,
                    dc,
                    SensorStateClass.MEASUREMENT,
                    value_fn=lambda c, s=sid: c.building_averages.get(s),
                )
            )

        # Per-meter annual sensors (current year)
        for meter in annual.cur_meters:
            sensors.append(
                MijnIstaSensor(
                    coordinator,
                    cuid,
                    f"svc{sid}_dev{meter.meter_id}_annual",
                    f"{label} {meter.serial_nr}",
                    unit,
                    dc,
                    SensorStateClass.TOTAL,
                    value_fn=lambda c, s=sid, mid=meter.meter_id: next(
                        (
                            m.c_value
                            for m in c.annual[s].cur_meters
                            if m.meter_id == mid
                        ),
                        None,
                    )
                    if s in c.annual
                    else None,
                    attrs_fn=lambda c, s=sid, mid=meter.meter_id: next(
                        (
                            m.as_dict()
                            for m in c.annual[s].cur_meters
                            if m.meter_id == mid
                        ),
                        {},
                    )
                    if s in c.annual
                    else {},
                    last_reset_fn=lambda c, s=sid, mid=meter.meter_id: _parse_dt(
                        next(
                            (
                                m.begin_date
                                for m in c.annual[s].cur_meters
                                if m.meter_id == mid
                            ),
                            "",
                        )
                    )
                    if s in c.annual
                    else None,
                )
            )

    # ── monthly sensors (per service) ───────────────────────────────────────
    # Scan all months newest-first; collect the first (most recent) MonthServiceData
    # per service so sensor creation is not blocked by an empty in-progress month.
    monthly_services: dict[int, Any] = {}  # sid → MonthServiceData
    for me in customer.monthly:
        for sid, msd in me.services.items():
            if sid not in monthly_services:
                monthly_services[sid] = msd

    for sid, month_svc in monthly_services.items():
        svc = svc_by_id.get(sid)
        unit = _ha_unit(svc.unit) if svc else None
        dc = _ha_device_class(svc.unit) if svc else None
        label = (
            _translate_service(svc.description, ha_lang)
            if svc
            else f"Service {sid}"
        )

        # Monthly total (most recent month with data, prior months in attributes)
        sensors.append(
            MijnIstaSensor(
                coordinator,
                cuid,
                f"svc{sid}_month_latest",
                f"{label} Month",
                unit,
                dc,
                SensorStateClass.TOTAL,
                value_fn=lambda c, s=sid: (
                    me.services[s].total_consumption
                    if (me := _find_month(c.monthly, s)) is not None
                    else None
                ),
                attrs_fn=lambda c, s=sid: (
                    {
                        "month": f"{me.year}-{me.month:02d}",
                        "building_average": me.services[s].building_average,
                        "has_approximation": me.services[s].has_approximation,
                        "prior_months": [
                            {
                                "year": entry.year,
                                "month": entry.month,
                                "consumption": entry.services[s].total_consumption
                                if s in entry.services
                                else None,
                                "building_average": entry.services[s].building_average
                                if s in entry.services
                                else None,
                            }
                            for entry in c.monthly
                            if not (entry.year == me.year and entry.month == me.month)
                        ][:12],
                    }
                    if (me := _find_month(c.monthly, s)) is not None
                    else {}
                ),
                last_reset_fn=lambda c, s=sid: (
                    datetime(me.year, me.month, 1, tzinfo=timezone.utc)
                    if (me := _find_month(c.monthly, s)) is not None
                    else None
                ),
            )
        )

        # Monthly building average
        sensors.append(
            MijnIstaSensor(
                coordinator,
                cuid,
                f"svc{sid}_month_building_avg",
                f"{label} Month Avg",
                unit,
                dc,
                SensorStateClass.MEASUREMENT,
                value_fn=lambda c, s=sid: (
                    me.services[s].building_average
                    if (me := _find_month(c.monthly, s)) is not None
                    else None
                ),
                attrs_fn=lambda c, s=sid: (
                    {"month": f"{me.year}-{me.month:02d}"}
                    if (me := _find_month(c.monthly, s)) is not None
                    else {}
                ),
            )
        )

        # Per physical meter, latest month
        for dev in month_svc.device_consumptions:
            sensors.append(
                MijnIstaSensor(
                    coordinator,
                    cuid,
                    f"svc{sid}_dev{dev.meter_id}_month",
                    f"{label} {dev.serial_nr} Month",
                    unit,
                    dc,
                    SensorStateClass.TOTAL,
                    value_fn=lambda c, s=sid, did=dev.meter_id: (
                        next(
                            (
                                d.c_value
                                for d in me.services[s].device_consumptions
                                if d.meter_id == did
                            ),
                            None,
                        )
                        if (me := _find_month(c.monthly, s)) is not None
                        else None
                    ),
                    attrs_fn=lambda c, s=sid, did=dev.meter_id: (
                        next(
                            (
                                d.as_dict()
                                for d in me.services[s].device_consumptions
                                if d.meter_id == did
                            ),
                            {},
                        )
                        if (me := _find_month(c.monthly, s)) is not None
                        else {}
                    ),
                    last_reset_fn=lambda c, s=sid: (
                        datetime(me.year, me.month, 1, tzinfo=timezone.utc)
                        if (me := _find_month(c.monthly, s)) is not None
                        else None
                    ),
                )
            )

    # ── average temperature (per billing period, from KNMI via ista) ────────
    sensors.append(
        MijnIstaSensor(
            coordinator,
            cuid,
            "avg_temp_current_period",
            "Temperature",
            UnitOfTemperature.CELSIUS,
            SensorDeviceClass.TEMPERATURE,
            SensorStateClass.MEASUREMENT,
            value_fn=lambda c: c.cur_period_temp,
            attrs_fn=lambda c: {
                "monthly_history": [
                    {"year": me.year, "month": me.month, "avg_temp": me.avg_temp}
                    for me in c.monthly[:24]
                    if me.avg_temp is not None
                ],
            },
        )
    )
    sensors.append(
        MijnIstaSensor(
            coordinator,
            cuid,
            "avg_temp_previous_period",
            "Temperature Previous",
            UnitOfTemperature.CELSIUS,
            SensorDeviceClass.TEMPERATURE,
            SensorStateClass.MEASUREMENT,
            value_fn=lambda c: c.prev_period_temp,
        )
    )

    return sensors


# ── platform setup ──────────────────────────────────────────────────────────


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up mijn.ista.nl sensors from a config entry."""
    coordinator: MijnIstaCoordinator = config_entry.runtime_data

    entities: list[MijnIstaSensor] = []
    if coordinator.data:
        for cuid, customer in coordinator.data.items():
            built = _build_sensors(coordinator, cuid, customer)
            _LOGGER.debug("Registering %d sensors for cuid=%s", len(built), cuid)
            entities.extend(built)

    async_add_entities(entities)
