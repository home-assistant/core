"""Sensor for the OMIE - Spain and Portugal electricity prices integration."""
from __future__ import annotations

from collections.abc import Mapping
import datetime as dt
from datetime import date, datetime, timedelta
import logging
import statistics
from typing import Any, TypeVar
from zoneinfo import ZoneInfo

from pyomie.model import OMIEResults
from pyomie.util import localize_hourly_data

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
from homeassistant.util.dt import utcnow

from .const import CET, DOMAIN
from .model import OMIESources

_DataT = TypeVar("_DataT")

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up OMIE from its config entry."""
    coordinators: OMIESources = hass.data[DOMAIN][entry.entry_id]

    device_info = DeviceInfo(
        configuration_url="https://www.omie.es/en/market-results",
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="OMI Group",
        name="OMIE",
        model="MIBEL market results",
    )

    class PriceEntity(SensorEntity):
        _entity_component_unrecorded_attributes = frozenset(
            {
                f"{day}_{attr}"
                for day in ("today", "tomorrow")
                for attr in ("average", "hours", "provisional")
            }
        )

        def __init__(self, sources: OMIESources, key: str) -> None:
            """Initialize the sensor."""
            self._attr_device_info = device_info
            self._attr_native_unit_of_measurement = (
                f"{CURRENCY_EURO}/{UnitOfEnergy.MEGA_WATT_HOUR}"
            )
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_unique_id = slugify(f"omie_{key}")
            self._attr_icon = "mdi:currency-eur"
            self._attr_should_poll = False
            self._attr_translation_key = key
            self._attr_has_entity_name = True
            self._key = key
            self._sources = sources
            self.entity_id = f"sensor.{self._attr_unique_id}"

        async def async_added_to_hass(self) -> None:
            """Register callbacks."""

            @callback
            def update() -> None:
                """Update this sensor's state."""
                cet_hourly_data = (
                    {}
                    | _pick_series_cet(self._sources.today.data, self._key)
                    | _pick_series_cet(self._sources.tomorrow.data, self._key)
                    | _pick_series_cet(self._sources.yesterday.data, self._key)
                )

                # times are formatted in the HA configured time zone and day boundaries are also
                # relative to the HA configured time zone.
                hass_tz = ZoneInfo(self.hass.config.time_zone)
                sensor_now = utcnow().astimezone(hass_tz)
                today_date = sensor_now.date()

                def day_hourly_data(day: date) -> Mapping[datetime, float | None]:
                    """Return a list of every hour in the given date in the HA timezone."""
                    day_hour0 = datetime(
                        day.year, day.month, day.day, tzinfo=hass_tz
                    ).astimezone(dt.UTC)

                    return {
                        hour: cet_hourly_data.get(hour.astimezone(CET))
                        for hour in [
                            (day_hour0 + timedelta(hours=i)).astimezone(hass_tz)
                            for i in range(25)
                        ]
                        if hour.date() == day  # 25th hour occurs on DST changeover only
                    }

                today_hourly_data = day_hourly_data(today_date)
                tomorrow_hourly_data = day_hourly_data(today_date + timedelta(days=1))

                # to work out the start of the current hour we truncate from minutes downwards
                # rather than create a new datetime to ensure correctness across DST boundaries
                sensor_hour = sensor_now.replace(minute=0, second=0, microsecond=0)

                self._attr_available = sensor_hour in today_hourly_data
                self._attr_native_value = today_hourly_data.get(sensor_hour)
                self._attr_extra_state_attributes = (
                    {}
                    | _day_attributes("today", today_hourly_data)
                    | _day_attributes("tomorrow", tomorrow_hourly_data)
                )

                self.async_schedule_update_ha_state()

            self.async_on_remove(self._sources.today.async_add_listener(update))
            self.async_on_remove(self._sources.tomorrow.async_add_listener(update))
            self.async_on_remove(self._sources.yesterday.async_add_listener(update))

    sensors = [
        PriceEntity(sources=coordinators, key="spot_price_pt"),
        PriceEntity(sources=coordinators, key="spot_price_es"),
    ]

    async_add_entities(sensors, update_before_add=True)
    for c in (coordinators.today, coordinators.tomorrow, coordinators.yesterday):
        await c.async_config_entry_first_refresh()


def _localize_hours(
    results: OMIEResults[_DataT], attr_name: str
) -> dict[dt.datetime, float]:
    """Localize incoming hourly data to the CET timezone."""
    localized = localize_hourly_data(
        results.market_date,
        getattr(results.contents, attr_name, []),
    )

    return {
        dt.datetime.fromisoformat(time).astimezone(CET): value
        for time, value in localized.items()
    }


def _day_attributes(
    day_name: str, hourly_data: Mapping[datetime, float | None]
) -> dict[str, Any]:
    return {
        f"{day_name}_average": _day_average(hourly_data),
        f"{day_name}_hours": hourly_data or None,
        f"{day_name}_provisional": _is_provisional(hourly_data),
    }


def _day_average(hours_in_day: Mapping[datetime, float | None]) -> float | None:
    """Return the arithmetic mean of the hours' prices if possible."""
    values = [v for v in (hours_in_day or {}).values() if v is not None]
    return None if len(values) == 0 else round(statistics.mean(values), 2)


def _is_provisional(hourly_data: Mapping[dt.datetime, float | None]) -> bool:
    """Return whether hourly data is incomplete."""
    return len(hourly_data or {}) == 0 or None in hourly_data.values()


def _pick_series_cet(
    res: OMIEResults[_DataT] | None,
    series_name: str,
) -> dict[dt.datetime, float]:
    """Pick the values for this series from the market data, keyed by a datetime in CET."""
    if res is None:
        return {}

    market_date = res.market_date
    series_data = getattr(res.contents, series_name, [])

    return {
        dt.datetime.fromisoformat(dt_str).astimezone(CET): v
        for dt_str, v in localize_hourly_data(market_date, series_data).items()
    }
