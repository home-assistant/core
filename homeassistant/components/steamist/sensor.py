"""Support for Steamist sensors."""
from __future__ import annotations

from typing import cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT, TIME_MINUTES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SteamistDataUpdateCoordinator
from .entity import SteamistEntity

_KEY_MINUTES_REMAIN = "minutes_remain"
_KEY_TEMP = "temp"

UNIT_MAPPINGS = {
    "C": TEMP_CELSIUS,
    "F": TEMP_FAHRENHEIT,
}

STEAMIST_SENSORS = (
    SensorEntityDescription(
        key=_KEY_MINUTES_REMAIN,
        name="Steam Minutes Remain",
        native_unit_of_measurement=TIME_MINUTES,
    ),
    SensorEntityDescription(
        key=_KEY_TEMP,
        name="Steam Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
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
            for description in STEAMIST_SENSORS
        ]
    )


class SteamistSensorEntity(SteamistEntity, SensorEntity):
    """Representation of an Steamist steam switch."""

    def __init__(
        self,
        coordinator: SteamistDataUpdateCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, entry, description)
        if description.key == _KEY_TEMP:
            self._attr_native_unit_of_measurement = UNIT_MAPPINGS[
                self._status.temp_units
            ]

    @property
    def native_value(self) -> int:
        """Return the native value of the sensor."""
        return cast(int, getattr(self._status, self.entity_description.key))
