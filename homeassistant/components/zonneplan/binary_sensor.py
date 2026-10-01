"""Binary sensor platform for Zonneplan."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from pyzonneplan import Battery

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import ZONNEPLAN_TIMEZONE
from .coordinator import ZonneplanConfigEntry, ZonneplanCoordinator
from .entity import ZonneplanBatteryEntity, ZonneplanEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ZonneplanBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Zonneplan binary sensor."""

    is_on_fn: Callable[[ZonneplanCoordinator], bool | None]


BINARY_SENSORS: tuple[ZonneplanBinarySensorEntityDescription, ...] = (
    ZonneplanBinarySensorEntityDescription(
        key="electricity_price_low",
        translation_key="electricity_price_low",
        is_on_fn=lambda coordinator: (
            block[0].start_date <= dt_util.utcnow() < block[1].end_date
            if coordinator.data.electricity_prices is not None
            and (
                block := coordinator.data.electricity_prices.price_block(
                    dt_util.now(ZONNEPLAN_TIMEZONE).date(),
                    ZONNEPLAN_TIMEZONE,
                    lowest=True,
                )
            )
            else None
        ),
    ),
)


@dataclass(frozen=True, kw_only=True)
class ZonneplanBatteryBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Zonneplan home battery binary sensor."""

    is_on_fn: Callable[[Battery], bool | None]


BATTERY_BINARY_SENSORS: tuple[ZonneplanBatteryBinarySensorEntityDescription, ...] = (
    ZonneplanBatteryBinarySensorEntityDescription(
        key="home_optimization_active",
        translation_key="home_optimization_active",
        is_on_fn=lambda battery: battery.home_optimization_active,
    ),
    ZonneplanBatteryBinarySensorEntityDescription(
        key="grid_congestion_active",
        translation_key="grid_congestion_active",
        is_on_fn=lambda battery: battery.grid_congestion_active,
    ),
    ZonneplanBatteryBinarySensorEntityDescription(
        key="dynamic_load_balancing_overload_active",
        translation_key="dynamic_load_balancing_overload_active",
        is_on_fn=lambda battery: battery.dynamic_load_balancing_overload_active,
    ),
    ZonneplanBatteryBinarySensorEntityDescription(
        key="backup_power_active",
        translation_key="backup_power_active",
        is_on_fn=lambda battery: battery.backup_power_active,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZonneplanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Zonneplan binary sensor platform."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        [
            *(
                ZonneplanBinarySensor(coordinator, description)
                for description in BINARY_SENSORS
            ),
            *(
                ZonneplanBatteryBinarySensor(battery, description)
                for battery in entry.runtime_data.batteries
                for description in BATTERY_BINARY_SENSORS
            ),
        ]
    )


class ZonneplanBinarySensor(ZonneplanEntity, BinarySensorEntity):
    """Representation of a Zonneplan binary sensor."""

    entity_description: ZonneplanBinarySensorEntityDescription

    @override
    async def async_added_to_hass(self) -> None:
        """Re-evaluate at every hour, as price blocks start and end on the hour."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._async_hour_changed, minute=0, second=0
            )
        )

    @callback
    def _async_hour_changed(self, now: datetime) -> None:
        """Write the state when a new hour starts."""
        self.async_write_ha_state()

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the current hour falls in the price block."""
        return self.entity_description.is_on_fn(self.coordinator)


class ZonneplanBatteryBinarySensor(ZonneplanBatteryEntity, BinarySensorEntity):
    """Representation of a Zonneplan home battery binary sensor."""

    entity_description: ZonneplanBatteryBinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.entity_description.is_on_fn(self.coordinator.data.battery)
