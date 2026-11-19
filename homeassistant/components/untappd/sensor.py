"""Sensors for the Untappd integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from aiountappd import Checkin

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import UntappdConfigEntry, UntappdData, UntappdDataUpdateCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class UntappdSensorEntityDescription(SensorEntityDescription):
    """Describe an Untappd sensor."""

    value_fn: Callable[[UntappdData], str | int | float | datetime | None]
    entity_picture_fn: Callable[[UntappdData], str | None] = lambda _: None


def _from_last_checkin[T](
    fn: Callable[[Checkin], T],
) -> Callable[[UntappdData], T | None]:
    """Return a function that reads a value from the last check-in, if any."""
    return lambda data: fn(data.last_checkin) if data.last_checkin else None


SENSORS: tuple[UntappdSensorEntityDescription, ...] = (
    UntappdSensorEntityDescription(
        key="total_checkins",
        translation_key="total_checkins",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.user.stats.total_checkins,
    ),
    UntappdSensorEntityDescription(
        key="total_beers",
        translation_key="total_beers",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.user.stats.total_beers,
    ),
    UntappdSensorEntityDescription(
        key="total_badges",
        translation_key="total_badges",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.user.stats.total_badges,
    ),
    UntappdSensorEntityDescription(
        key="total_friends",
        translation_key="total_friends",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.user.stats.total_friends,
    ),
    UntappdSensorEntityDescription(
        key="last_checkin",
        translation_key="last_checkin",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_from_last_checkin(lambda checkin: checkin.created_at),
    ),
    UntappdSensorEntityDescription(
        key="last_beer",
        translation_key="last_beer",
        value_fn=_from_last_checkin(lambda checkin: checkin.beer.beer_name),
        entity_picture_fn=_from_last_checkin(
            lambda checkin: checkin.beer.beer_label or None
        ),
    ),
    UntappdSensorEntityDescription(
        key="last_brewery",
        translation_key="last_brewery",
        value_fn=_from_last_checkin(lambda checkin: checkin.brewery.brewery_name),
    ),
    UntappdSensorEntityDescription(
        key="last_rating",
        translation_key="last_rating",
        suggested_display_precision=2,
        # A rating of 0 means the check-in was not rated.
        value_fn=_from_last_checkin(lambda checkin: checkin.rating_score or None),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UntappdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Untappd sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        UntappdSensor(coordinator, description) for description in SENSORS
    )


class UntappdSensor(CoordinatorEntity[UntappdDataUpdateCoordinator], SensorEntity):
    """An Untappd sensor."""

    entity_description: UntappdSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UntappdDataUpdateCoordinator,
        description: UntappdSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        user = coordinator.data.user
        self._attr_unique_id = f"{user.uid}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(user.uid))},
            name=user.user_name,
            manufacturer="Untappd",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=user.untappd_url,
        )

    @property
    @override
    def native_value(self) -> str | int | float | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return the picture of the sensor."""
        return self.entity_description.entity_picture_fn(self.coordinator.data)
