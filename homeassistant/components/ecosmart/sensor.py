"""Sensor platform for the ecosmart integration."""

from typing import Any, override

from aioecosmart import Forecast, IcpScope, Spot

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import UNIT_CENTS_PER_KWH
from .coordinator import EcosmartConfigEntry, EcosmartCoordinator
from .entity import EcosmartEntity

# Everything on screen comes from two coordinators, so entities never talk to
# the API themselves and need no update throttling.
PARALLEL_UPDATES = 0

SPOT_PRICE_DESCRIPTION = SensorEntityDescription(
    key="spot_price",
    translation_key="spot_price",
    native_unit_of_measurement=UNIT_CENTS_PER_KWH,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=2,
)

FORECAST_PRICE_DESCRIPTION = SensorEntityDescription(
    key="forecast_price",
    translation_key="forecast_price",
    native_unit_of_measurement=UNIT_CENTS_PER_KWH,
    suggested_display_precision=2,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EcosmartConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up two price sensors for every connection point on the key."""
    runtime_data = entry.runtime_data
    async_add_entities(
        sensor
        for icp in runtime_data.identity.allowed_icps
        for sensor in (
            EcosmartSpotPriceSensor(runtime_data.spot_coordinator, icp),
            EcosmartForecastPriceSensor(runtime_data.forecast_coordinator, icp),
        )
    )


class EcosmartSpotPriceSensor(EcosmartEntity[Spot], SensorEntity):
    """The price of electricity right now, GST inclusive.

    Deliberately unavailable rather than stale: a price more than about fifteen
    minutes old must never be what tells a battery to charge.
    """

    def __init__(self, coordinator: EcosmartCoordinator[Spot], icp: IcpScope) -> None:
        """Initialise the spot price sensor."""
        super().__init__(coordinator, icp, SPOT_PRICE_DESCRIPTION)

    @property
    @override
    def available(self) -> bool:
        """Return True only while a fresh, priced observation is in hand."""
        spot = self._price_data
        return (
            super().available
            and not spot.is_stale
            and spot.price_cents_per_kwh_incl_gst is not None
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current price in cents per kWh including GST."""
        return self._price_data.price_cents_per_kwh_incl_gst

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the same price in the market's other units, plus its age."""
        spot = self._price_data
        return {
            "price_cents_per_kwh_excl_gst": spot.price_cents_per_kwh,
            "price_dollars_per_mwh": spot.price_dollars_per_mwh,
            "observed_at": (
                None if spot.observed_at is None else spot.observed_at.isoformat()
            ),
            "gst_rate_percent": spot.gst_rate_percent,
        }


class EcosmartForecastPriceSensor(EcosmartEntity[Forecast], SensorEntity):
    """The forecast price for the half-hour now in progress, GST inclusive.

    The whole published curve rides along as an attribute so automations can
    plan ahead. It is kept out of the recorder: up to 96 points every half hour
    would bloat the database and none of it is worth keeping once superseded.
    """

    _unrecorded_attributes = frozenset({"points"})

    def __init__(
        self, coordinator: EcosmartCoordinator[Forecast], icp: IcpScope
    ) -> None:
        """Initialise the forecast price sensor."""
        super().__init__(coordinator, icp, FORECAST_PRICE_DESCRIPTION)

    @property
    @override
    def available(self) -> bool:
        """Return True only while the published schedules reach this far."""
        return super().available and bool(self._price_data.points)

    @property
    @override
    def native_value(self) -> float | None:
        """Return the first forecast half-hour in cents per kWh including GST."""
        points = self._price_data.points
        return points[0].price_cents_per_kwh_incl_gst if points else None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the whole forward curve and how far it actually reaches."""
        forecast = self._price_data
        return {
            "points": [
                {
                    "starts_at": point.starts_at.isoformat(),
                    "trading_date": point.trading_date.isoformat(),
                    "trading_period": point.trading_period,
                    "schedule": point.schedule.value,
                    "price_cents_per_kwh_incl_gst": point.price_cents_per_kwh_incl_gst,
                    "price_cents_per_kwh_excl_gst": point.price_cents_per_kwh,
                    "price_dollars_per_mwh": point.price_dollars_per_mwh,
                }
                for point in forecast.points
            ],
            "covered_hours": forecast.covered_hours,
            "published_at": (
                None
                if forecast.published_at is None
                else forecast.published_at.isoformat()
            ),
        }
