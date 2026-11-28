"""Sensor platform for the Osmund integration: today's electricity prices at each location."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import fmean
from typing import override

from osmund import API_ACCESS_OPEN, Location, PriceDay, PriceInterval

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change

from .coordinator import OsmundConfigEntry, OsmundCoordinator, danish_now
from .entity import OsmundEntity

# Everything comes from the coordinator; no sensor calls the API.
PARALLEL_UPDATES = 0

PRICE_UNIT = f"DKK/{UnitOfEnergy.KILO_WATT_HOUR}"


@dataclass(frozen=True, slots=True)
class Prices:
    """The price days held for a location, at a moment.

    Moments are compared in UTC: two datetimes with the same time zone are
    compared by their wall clock, and when the clocks go back, the hour from
    02:00 comes twice.
    """

    now: datetime
    today: PriceDay
    tomorrow: PriceDay | None

    def current(self) -> PriceInterval | None:
        """The interval that holds now."""
        return self.today.at(self.now.astimezone(UTC))

    def following(self) -> PriceInterval | None:
        """The interval after the current one, which may be tomorrow's first."""
        if (current := self.current()) is None:
            return None
        intervals = self.today.intervals + (
            self.tomorrow.intervals if self.tomorrow else ()
        )
        end = current.end.timestamp()
        return next((i for i in intervals if i.start.timestamp() == end), None)

    def lowest(self) -> PriceInterval | None:
        """Today's cheapest interval; the earliest of equal ones."""
        return min(self.today.intervals, key=lambda i: i.total_inc_vat, default=None)

    def highest(self) -> PriceInterval | None:
        """Today's most expensive interval; the earliest of equal ones."""
        return max(self.today.intervals, key=lambda i: i.total_inc_vat, default=None)

    def average(self) -> float | None:
        """Today's average price; every interval of a day is equally long."""
        if not self.today.intervals:
            return None
        return fmean(i.total_inc_vat for i in self.today.intervals)


def _price(interval: PriceInterval | None) -> float | None:
    return interval.total_inc_vat if interval else None


def _start(interval: PriceInterval | None) -> datetime | None:
    return interval.start if interval else None


@dataclass(frozen=True, kw_only=True)
class OsmundPriceDescription(SensorEntityDescription):
    """A price sensor: what it shows of the held prices."""

    value_fn: Callable[[Prices], float | datetime | None]


# No device class for the prices: there is none for a price per kWh. They are
# in DKK/kWh with VAT.
SENSORS: tuple[OsmundPriceDescription, ...] = (
    OsmundPriceDescription(
        key="price_now",
        translation_key="price_now",
        native_unit_of_measurement=PRICE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda prices: _price(prices.current()),
    ),
    OsmundPriceDescription(
        key="price_next",
        translation_key="price_next",
        native_unit_of_measurement=PRICE_UNIT,
        suggested_display_precision=2,
        value_fn=lambda prices: _price(prices.following()),
    ),
    OsmundPriceDescription(
        key="price_lowest_today",
        translation_key="price_lowest_today",
        native_unit_of_measurement=PRICE_UNIT,
        suggested_display_precision=2,
        value_fn=lambda prices: _price(prices.lowest()),
    ),
    OsmundPriceDescription(
        key="price_highest_today",
        translation_key="price_highest_today",
        native_unit_of_measurement=PRICE_UNIT,
        suggested_display_precision=2,
        value_fn=lambda prices: _price(prices.highest()),
    ),
    OsmundPriceDescription(
        key="price_average_today",
        translation_key="price_average_today",
        native_unit_of_measurement=PRICE_UNIT,
        suggested_display_precision=2,
        value_fn=lambda prices: prices.average(),
    ),
    OsmundPriceDescription(
        key="price_lowest_today_time",
        translation_key="price_lowest_today_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda prices: _start(prices.lowest()),
    ),
    OsmundPriceDescription(
        key="price_highest_today_time",
        translation_key="price_highest_today_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda prices: _start(prices.highest()),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OsmundConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the price sensors of every location with API access.

    A location whose prices could not be read yet still gets its sensors: they
    are unavailable, and they keep the coordinator polling until it can.
    """
    coordinator = entry.runtime_data
    async_add_entities(
        OsmundPriceSensor(coordinator, location, description)
        for location in coordinator.data.locations.values()
        if location.api_access == API_ACCESS_OPEN
        for description in SENSORS
    )


class OsmundPriceSensor(OsmundEntity, SensorEntity):
    """A price at one location, from the price days the coordinator holds."""

    entity_description: OsmundPriceDescription

    def __init__(
        self,
        coordinator: OsmundCoordinator,
        location: Location,
        description: OsmundPriceDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, location, description.key)
        self.entity_description = description

    @override
    async def async_added_to_hass(self) -> None:
        """Show the new price on each quarter hour and at midnight, without a call."""
        await super().async_added_to_hass()

        @callback
        def _tick(_now: datetime) -> None:
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_time_change(self.hass, _tick, minute=(0, 15, 30, 45), second=1)
        )

    @property
    @override
    def available(self) -> bool:
        """When the last update worked and the API answers for the location."""
        return super().available and self.location_id in self.coordinator.data.prices

    @property
    @override
    def native_value(self) -> float | datetime | None:
        """The value; unknown while today's prices are not there."""
        now = danish_now()
        days = self.coordinator.data.prices.get(self.location_id, {})
        if (today := days.get(now.date())) is None:
            return None
        tomorrow = days.get(now.date() + timedelta(days=1))
        return self.entity_description.value_fn(Prices(now, today, tomorrow))
