"""Sensor for the OMIE - Spain and Portugal electricity prices integration."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import Any, TypeVar, cast
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO, STATE_UNKNOWN, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
from homeassistant.util.dt import utcnow

from .const import CET, DOMAIN
from .model import OMIESources
from .util import _pick_series_cet, enumerate_hours_of_day

_DataT = TypeVar("_DataT")

_LOGGER = logging.getLogger(__name__)

_ATTRIBUTION = "Data provided by OMIE.es"

_UNRECORDED_ATTRIBUTES = frozenset(
    {
        f"{day}_{attr}"
        for day in ("today", "tomorrow")
        for attr in ("hours", "provisional")
    }
)


@dataclass(frozen=True)
class OMIEPriceEntityDescription(SensorEntityDescription):
    """Describes OMIE price entities."""

    def __init__(self, key: str) -> None:
        """Construct an OMIEPriceEntityDescription that reports prices in €/MWh."""
        super().__init__(
            key=key,
            has_entity_name=True,
            translation_key=key,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.MEGA_WATT_HOUR}",
            icon="mdi:currency-eur",
        )


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

    def hass_tzinfo() -> ZoneInfo:
        return ZoneInfo(hass.config.time_zone)

    class OMIEPriceEntity(SensorEntity):
        _entity_component_unrecorded_attributes = _UNRECORDED_ATTRIBUTES

        def __init__(self, description: OMIEPriceEntityDescription) -> None:
            """Initialize the sensor."""
            self.entity_description = description
            self._attr_device_info = device_info
            self._attr_unique_id = slugify(description.key)
            self._attr_should_poll = False
            self._attr_attribution = _ATTRIBUTION

        async def async_added_to_hass(self) -> None:
            """Register callbacks."""

            @callback
            def update() -> None:
                """Update this sensor's state from the coordinator results."""

                # times are formatted in the HA configured time zone
                hass_now = utcnow().astimezone(hass_tzinfo())

                # day boundaries are also relative to the HA configured time zone.
                today: date = hass_now.date()
                tomorrow: date = today + timedelta(days=1)
                _, today_hours, tomorrow_hours = self._omie_hourly_data(today, tomorrow)

                # to work out the start of the current hour we truncate from minutes downwards
                # rather than create a new datetime to ensure correctness across DST boundaries
                hour_start = hass_now.replace(minute=0, second=0, microsecond=0)

                self._attr_available = hour_start in today_hours
                self._attr_native_value = today_hours.get(hour_start, STATE_UNKNOWN)
                self._attr_extra_state_attributes = (
                    {}
                    | _format_day_attributes("today", today_hours)
                    | _format_day_attributes("tomorrow", tomorrow_hours)
                )

                self.async_schedule_update_ha_state()

            self.async_on_remove(coordinators.today.async_add_listener(update))
            self.async_on_remove(coordinators.tomorrow.async_add_listener(update))
            self.async_on_remove(coordinators.yesterday.async_add_listener(update))

        def _omie_hourly_data(self, *dates: date) -> list[dict[datetime, float | None]]:
            """Return a non-empty list containing all known OMIE hourly data in the first element and optionally more elements, one per date.

            @param dates: a list of `datetime.date`
            @return: a non-empty list
            """
            pyomie_series_key = self.entity_description.key
            all_hours_cet: dict[datetime, float] = (
                {}
                | _pick_series_cet(coordinators.today.data, pyomie_series_key)
                | _pick_series_cet(coordinators.tomorrow.data, pyomie_series_key)
                | _pick_series_cet(coordinators.yesterday.data, pyomie_series_key)
            )

            hass_tz = hass_tzinfo()

            first = cast(dict[datetime, float | None], all_hours_cet)
            rest = [_hours_of_day(all_hours_cet, hass_tz, day) for day in dates]

            return [first] + rest

    sensors = [
        OMIEPriceEntity(OMIEPriceEntityDescription("spot_price_pt")),
        OMIEPriceEntity(OMIEPriceEntityDescription("spot_price_es")),
    ]

    async_add_entities(sensors, update_before_add=True)
    for c in (coordinators.today, coordinators.tomorrow, coordinators.yesterday):
        await c.async_config_entry_first_refresh()


def _hours_of_day(
    hours: Mapping[datetime, _DataT], time_zone: ZoneInfo, day: date
) -> dict[datetime, _DataT | None]:
    return {
        hour: hours.get(hour.astimezone(CET))
        for hour in enumerate_hours_of_day(time_zone, day)
    }


def _format_day_attributes(
    day_name: str, hourly_data: Mapping[datetime, _DataT | None]
) -> dict[str, Any]:
    return {
        f"{day_name}_hours": hourly_data,
        f"{day_name}_provisional": len(hourly_data or {}) == 0
        or None in hourly_data.values(),
    }
