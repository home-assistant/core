"""Coordinator for mijn.ista.nl."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from mijn_ista_api import MijnIstaAPI, MijnIstaAuthError, MijnIstaConnectionError
from .const import CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


# ── data model ──────────────────────────────────────────────────────────────


@dataclass
class AnnualMeterSummary:
    """Meter-level reading for one annual period."""

    meter_id: int
    service_id: int
    serial_nr: int
    art_nr: int
    begin_date: str
    begin_value: float
    end_date: str
    end_value: float
    c_value: float
    dec_pos: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "meter_id": self.meter_id,
            "service_id": self.service_id,
            "serial_nr": self.serial_nr,
            "art_nr": self.art_nr,
            "begin_date": self.begin_date,
            "begin_value": self.begin_value,
            "end_date": self.end_date,
            "end_value": self.end_value,
            "consumption": self.c_value,
        }


@dataclass
class AnnualSummary:
    """Annual current-vs-previous comparison for one service."""

    service_id: int
    total_now: float
    total_previous: float
    diff_pct: float
    total_whole_previous: float
    dec_pos: int
    cur_meters: list[AnnualMeterSummary]
    comp_meters: list[AnnualMeterSummary]


@dataclass
class DeviceConsumption:
    """Consumption reading for one physical meter in one month."""

    meter_id: int
    serial_nr: int
    art_nr: int
    s_date: str
    s_value: float
    e_date: str
    e_value: float
    c_value: float
    ccd_value: float
    active: str
    main_device: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "meter_id": self.meter_id,
            "serial_nr": self.serial_nr,
            "art_nr": self.art_nr,
            "begin_date": self.s_date,
            "begin_value": self.s_value,
            "end_date": self.e_date,
            "end_value": self.e_value,
            "consumption": self.c_value,
            "active_since": self.active,
            "main_device": self.main_device,
        }


@dataclass
class MonthServiceData:
    """One service's data for a single calendar month."""

    service_id: int
    total_consumption: float
    building_average: float
    has_approximation: bool
    device_consumptions: list[DeviceConsumption]


@dataclass
class MonthEntry:
    """All services' data for a single calendar month."""

    year: int
    month: int
    avg_temp: float | None
    services: dict[int, MonthServiceData] = field(
        default_factory=dict
    )  # keyed by service_id


@dataclass
class ServiceInfo:
    """Metadata about one billing service (heating, electricity, water…)."""

    id: int
    description: str
    meter_type: str
    unit: str


@dataclass
class CustomerData:
    """All data for one property (Cuid)."""

    cuid: str
    address: str
    zip_code: str
    city: str
    date_start: str
    services: list[ServiceInfo]
    billing_periods: list[dict[str, Any]]
    annual: dict[int, AnnualSummary]  # keyed by service_id
    monthly: list[MonthEntry]  # newest first
    building_averages: dict[int, float]  # service_id → NormalizedValue
    cur_period_temp: float | None  # avg outdoor temp for current billing period
    prev_period_temp: float | None  # avg outdoor temp for previous billing period


# ── parsing helpers (pure functions, easy to unit-test) ─────────────────────


def _parse_annual_meter(m: dict[str, Any]) -> AnnualMeterSummary:
    return AnnualMeterSummary(
        meter_id=m["MeterId"],
        service_id=m["serviceId"],
        serial_nr=m.get("MeterNr", 0),
        art_nr=m.get("ArtNr", 0),
        begin_date=m.get("BsDate", ""),
        begin_value=m.get("BeginValue", 0.0),
        end_date=m.get("EsDate", ""),
        end_value=m.get("EndValue", 0.0),
        c_value=m.get("CValue", 0.0),
        dec_pos=m.get("DecPos", 0),
    )


def _parse_device_consumption(d: dict[str, Any]) -> DeviceConsumption:
    return DeviceConsumption(
        meter_id=d["Id"],
        serial_nr=d.get("SerialNr", 0),
        art_nr=d.get("ArtNr", 0),
        s_date=d.get("SDate", ""),
        s_value=d.get("SValue", 0.0),
        e_date=d.get("EDate", ""),
        e_value=d.get("EValue", 0.0),
        c_value=d.get("CValue", 0.0),
        ccd_value=d.get("CCDValue", 0.0),
        active=d.get("Active", ""),
        main_device=d.get("MainDevice"),
    )


def _parse_customer(
    cus: dict[str, Any],
    month_data: dict[str, Any],
    avg_data: dict[str, Any],
) -> CustomerData:
    """Convert raw API dicts into a structured CustomerData object."""
    cur = cus.get("curConsumption", {})

    services = [
        ServiceInfo(
            id=s["Id"],
            description=s.get("Description", ""),
            meter_type=s.get("MeterType", ""),
            unit=s.get("Unit", ""),
        )
        for s in cur.get("Billingservices", [])
    ]

    annual: dict[int, AnnualSummary] = {}
    for sc in cur.get("ServicesComp", []):
        sid = sc["Id"]
        annual[sid] = AnnualSummary(
            service_id=sid,
            total_now=sc.get("TotalNow", 0.0),
            total_previous=sc.get("TotalPrevious", 0.0),
            diff_pct=sc.get("TotalDiffperc", 0.0),
            total_whole_previous=sc.get("TotalWholePrevious", 0.0),
            dec_pos=sc.get("DecPos", 0),
            cur_meters=[_parse_annual_meter(m) for m in sc.get("CurMeters", [])],
            comp_meters=[_parse_annual_meter(m) for m in sc.get("CompMeters", [])],
        )

    monthly: list[MonthEntry] = []
    for mc in month_data.get("mc", []):
        svc_map: dict[int, MonthServiceData] = {}
        for sc in mc.get("ServiceConsumptions", []):
            sid = sc["ServiceId"]
            svc_map[sid] = MonthServiceData(
                service_id=sid,
                total_consumption=sc.get("TotalConsumption", 0.0),
                building_average=sc.get("BuldingAverage", 0.0),
                has_approximation=sc.get("HasApproximation", False),
                device_consumptions=[
                    _parse_device_consumption(d)
                    for d in sc.get("DeviceConsumptions", [])
                ],
            )
        monthly.append(
            MonthEntry(
                year=mc["y"],
                month=mc["m"],
                avg_temp=mc.get("at")
                or None,  # null/0 → None (KNMI data not yet available)
                services=svc_map,
            )
        )
    # API returns months in unspecified order; sort newest-first so index 0
    # is always the most recent entry (even if it has empty ServiceConsumptions).
    monthly.sort(key=lambda m: (m.year, m.month), reverse=True)

    building_averages: dict[int, float] = {
        a["BillingServiceId"]: a.get("NormalizedValue", 0.0)
        for a in avg_data.get("Averages", [])
    }

    # Extract average outdoor temperature per billing period (from KNMI via ista)
    billing_periods = cur.get("BillingPeriods", [])
    sorted_periods = sorted(billing_periods, key=lambda p: p.get("y", 0), reverse=True)
    cur_period_temp = sorted_periods[0].get("ta") or None if sorted_periods else None
    prev_period_temp = (
        sorted_periods[1].get("ta") or None if len(sorted_periods) > 1 else None
    )

    return CustomerData(
        cuid=cus["Cuid"],
        address=cus.get("Adress", ""),
        zip_code=cus.get("Zip", ""),
        city=cus.get("City", ""),
        date_start=cus.get("DateStart", ""),
        services=services,
        billing_periods=billing_periods,
        annual=annual,
        monthly=monthly,
        building_averages=building_averages,
        cur_period_temp=cur_period_temp,
        prev_period_temp=prev_period_temp,
    )


# ── coordinator ─────────────────────────────────────────────────────────────


class MijnIstaCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator for mijn.ista.nl.

    Fetches data from three API endpoints per property (Cuid) and
    structures it into CustomerData objects keyed by Cuid.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: MijnIstaAPI,
    ) -> None:
        self.api = api
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}-{entry.entry_id}",
            update_method=self._async_update_data,
            update_interval=timedelta(
                hours=entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            ),
        )

    async def _async_update_data(self) -> dict[str, CustomerData]:
        try:
            await self.api.authenticate()
            user_data = await self.api.get_user_values()

            result: dict[str, CustomerData] = {}

            for cus in user_data.get("Cus", []):
                cuid = cus["Cuid"]
                cur = cus.get("curConsumption", {})
                periods = cur.get("BillingPeriods", [])

                # Find current year's billing period (for ConsumptionAverages date range)
                now_year = dt_util.now().year
                cur_period = next(
                    (p for p in periods if p.get("y") == now_year),
                    periods[0] if periods else None,
                )

                if cur_period:
                    month_data, avg_data = await asyncio.gather(
                        self.api.get_month_values(cuid),
                        self.api.get_consumption_averages(
                            cuid,
                            cur_period["s"][:10],
                            cur_period["e"][:10],
                        ),
                    )
                else:
                    month_data = await self.api.get_month_values(cuid)
                    avg_data = {"Averages": []}

                result[cuid] = _parse_customer(cus, month_data, avg_data)
                _LOGGER.debug(
                    "mijn.ista.nl: loaded %d monthly entries for %s",
                    len(result[cuid].monthly),
                    cuid,
                )

            return result

        except MijnIstaAuthError as exc:
            raise ConfigEntryAuthFailed from exc
        except MijnIstaConnectionError as exc:
            raise UpdateFailed(str(exc)) from exc
