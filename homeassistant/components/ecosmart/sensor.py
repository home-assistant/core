"""Sensor platform for the ecosmart integration."""

from typing import override

from aioecosmart import IcpScope

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

# Everything on screen comes from the coordinator, so entities never talk to
# the API themselves and need no update throttling.
PARALLEL_UPDATES = 0

SPOT_PRICE_DESCRIPTION = SensorEntityDescription(
    key="spot_price",
    translation_key="spot_price",
    native_unit_of_measurement=UNIT_CENTS_PER_KWH,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=2,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EcosmartConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a spot price sensor for every connection point on the key."""
    coordinator = entry.runtime_data
    async_add_entities(
        EcosmartSpotPriceSensor(coordinator, icp)
        for icp in coordinator.identity.allowed_icps
    )


class EcosmartSpotPriceSensor(EcosmartEntity, SensorEntity):
    """The price of electricity right now, GST inclusive.

    Unavailable whenever the last fetch failed, and also while the fetched
    price is stale: a price more than about fifteen minutes old must never be
    what tells a battery to charge.
    """

    def __init__(self, coordinator: EcosmartCoordinator, icp: IcpScope) -> None:
        """Initialise the spot price sensor."""
        super().__init__(coordinator, icp, SPOT_PRICE_DESCRIPTION)

    @property
    @override
    def available(self) -> bool:
        """Return True only while a fresh, priced observation is in hand."""
        return (
            super().available
            and not self.spot.is_stale
            and self.spot.price_cents_per_kwh_incl_gst is not None
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current price in cents per kWh including GST."""
        return self.spot.price_cents_per_kwh_incl_gst
