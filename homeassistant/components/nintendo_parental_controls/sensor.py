"""Sensor platform for Nintendo parental controls."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from pynintendoparental.player import Player

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NintendoParentalControlsConfigEntry, NintendoUpdateCoordinator
from .entity import Device, NintendoDevice

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


class NintendoParentalControlsSensor(StrEnum):
    """Store keys for Nintendo parental controls sensors."""

    PLAYING_TIME = "playing_time"
    PLAYER_PLAYING_TIME = "player_playing_time"
    TIME_REMAINING = "time_remaining"
    TIME_EXTENDED = "time_extended"


@dataclass(kw_only=True, frozen=True)
class NintendoParentalControlsDeviceSensorEntityDescription(SensorEntityDescription):
    """Description for Nintendo parental controls device sensor entities."""

    value_fn: Callable[[Device], datetime | int | float | None]
    available_fn: Callable[[Device], bool] = lambda device: True


@dataclass(kw_only=True, frozen=True)
class NintendoParentalControlsPlayerSensorEntityDescription(SensorEntityDescription):
    """Description for Nintendo parental controls player sensor entities."""

    value_fn: Callable[[Player], int | float | None]


DEVICE_SENSOR_DESCRIPTIONS: tuple[
    NintendoParentalControlsDeviceSensorEntityDescription, ...
] = (
    NintendoParentalControlsDeviceSensorEntityDescription(
        key=NintendoParentalControlsSensor.PLAYING_TIME,
        translation_key=NintendoParentalControlsSensor.PLAYING_TIME,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.today_playing_time,
    ),
    NintendoParentalControlsDeviceSensorEntityDescription(
        key=NintendoParentalControlsSensor.TIME_REMAINING,
        translation_key=NintendoParentalControlsSensor.TIME_REMAINING,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.today_time_remaining,
    ),
    NintendoParentalControlsSensorEntityDescription(
        key=NintendoParentalControlsSensor.TIME_EXTENDED,
        translation_key=NintendoParentalControlsSensor.TIME_EXTENDED,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.extra_playing_time,
        available_fn=lambda device: device.extra_playing_time is not None,
    ),
)

PLAYER_SENSOR_DESCRIPTIONS: tuple[
    NintendoParentalControlsPlayerSensorEntityDescription, ...
] = (
    NintendoParentalControlsPlayerSensorEntityDescription(
        key=NintendoParentalControlsSensor.PLAYER_PLAYING_TIME,
        translation_key=NintendoParentalControlsSensor.PLAYER_PLAYING_TIME,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda player: player.playing_time,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NintendoParentalControlsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_entities(
        NintendoParentalControlsDeviceSensorEntity(entry.runtime_data, device, sensor)
        for device in entry.runtime_data.api.devices.values()
        for sensor in DEVICE_SENSOR_DESCRIPTIONS
    )
    for device in entry.runtime_data.api.devices.values():
        async_add_entities(
            NintendoParentalControlsPlayerSensorEntity(
                entry.runtime_data, device, player, sensor
            )
            for player in device.players
            for sensor in PLAYER_SENSOR_DESCRIPTIONS
        )


class NintendoParentalControlsDeviceSensorEntity(NintendoDevice, SensorEntity):
    """Represent a single sensor."""

    entity_description: NintendoParentalControlsDeviceSensorEntityDescription

    def __init__(
        self,
        coordinator: NintendoUpdateCoordinator,
        device: Device,
        description: NintendoParentalControlsDeviceSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator, device=device, key=description.key)
        self.entity_description = description

    @property
    def native_value(self) -> datetime | int | float | None:
        """Return the native value."""
        return self.entity_description.value_fn(self._device)

    @property
    def available(self) -> bool:
        """Return if the sensor is available."""
        return super().available and self.entity_description.available_fn(self._device)


class NintendoParentalControlsPlayerSensorEntity(NintendoDevice, SensorEntity):
    """Represent a single player sensor."""

    entity_description: NintendoParentalControlsPlayerSensorEntityDescription
    _unrecorded_attributes = frozenset({"games"})

    def __init__(
        self,
        coordinator: NintendoUpdateCoordinator,
        device: Device,
        player: str,
        description: NintendoParentalControlsPlayerSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator, device=device, key=description.key)
        self.entity_description = description
        self.player_id = player
        self._attr_translation_placeholders = {
            "nickname": device.get_player(player).nickname  # type: ignore[dict-item]
        }
        self._attr_unique_id = f"{player}_{description.key}"

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture."""
        return self._device.get_player(self.player_id).player_image

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.entity_description.value_fn(self._device.get_player(self.player_id))

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra state attributes."""
        return {
            "games": [
                {
                    "title": app["meta"]["title"],
                    "playing_time": app["playingTime"],
                    "image": app["meta"]["imageUri"]["medium"],
                    "shop": app["meta"]["shopUri"],
                }
                for app in self._device.get_player(self.player_id).apps
            ]
        }
