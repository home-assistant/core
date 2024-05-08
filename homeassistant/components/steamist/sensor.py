"""Support for Steamist sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aiosteamist import SteamistStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SteamistDataUpdateCoordinator
from .entity import SteamistEntity

_KEY_MINUTES_REMAIN = "minutes_remain"
_KEY_TEMP = "temp"

UNIT_MAPPINGS = {
    "C": UnitOfTemperature.CELSIUS,
    "F": UnitOfTemperature.FAHRENHEIT,
}


@dataclass(frozen=True)
class SteamistSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[SteamistStatus], int | None]


@dataclass(frozen=True)
class SteamistSensorEntityDescription(
    SensorEntityDescription, SteamistSensorEntityDescriptionMixin
):
    """Describes a Steamist sensor entity."""


SENSORS: tuple[SteamistSensorEntityDescription, ...] = (
    SteamistSensorEntityDescription(
        key=_KEY_MINUTES_REMAIN,
        translation_key="steam_minutes_remain",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda status: status.minutes_remain,
    ),
    SteamistSensorEntityDescription(
        key=_KEY_TEMP,
        translation_key="steam_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.temp,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: SteamistDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    async_add_entities(
        [
            SteamistSensorEntity(coordinator, config_entry, description)
            for description in SENSORS
        ]
    )


class SteamistSensorEntity(SteamistEntity, SensorEntity):
    """Representation of a Steamist steam switch."""

    entity_description: SteamistSensorEntityDescription

    def __init__(
        self,
        coordinator: SteamistDataUpdateCoordinator,
        entry: ConfigEntry,
        description: SteamistSensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, entry, description)
        if description.key == _KEY_TEMP:
            self._attr_native_unit_of_measurement = UNIT_MAPPINGS[
                self._status.temp_units
            ]

    @property
    def native_value(self) -> int | None:
        """Return the native value of the sensor."""
        return self.entity_description.value_fn(self._status)
