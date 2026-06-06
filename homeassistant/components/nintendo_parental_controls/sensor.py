"""Sensor platform for Nintendo parental controls."""

from collections.abc import Callable
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
from homeassistant.util import dt as dt_util

from .coordinator import NintendoParentalControlsConfigEntry, NintendoUpdateCoordinator
from .entity import Device, NintendoDevice

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

import logging
_LOGGER = logging.getLogger(__name__)


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
    attributes_fn: Callable[[Device], dict | None] = lambda device: None


@dataclass(kw_only=True, frozen=True)
class NintendoParentalControlsPlayerSensorEntityDescription(SensorEntityDescription):
    """Description for Nintendo parental controls player sensor entities."""

    value_fn: Callable[[Player], int | float | None]


def _build_daily_attributes(device: Device) -> dict | None:
    """Build daily summaries and applications attributes.

    Exposes the last 5 days of play history and a full list of applications
    with today's playtime per app.

    Supports both the legacy daily-summary API schema (Switch, Switch Lite)
    and the updated schema introduced with Switch 2, where player data uses
    ``players``/``playedGames`` instead of ``devicePlayers``/``playedApps``.

    When multiple players are active simultaneously, Nintendo reports the same
    console playtime for each player. To avoid multiplying the actual playtime,
    ``max()`` is used instead of summing across players.
    """
    try:
        if not device.daily_summaries or not isinstance(device.daily_summaries, list):
            return None

        today_str = dt_util.now().strftime("%Y-%m-%d")
        today_summary = device.daily_summaries[0]
        is_today = today_summary.get("date") == today_str

        daily = [
            {
                "date": s.get("date"),
                "playingTime": s.get("playingTime"),
                "playedApps": [
                    {
                        "title": a.get("title"),
                        "applicationId": a.get("applicationId"),
                        "imageUri": a.get("imageUri", {}),
                        "playingTime": a.get("playingTime"),
                        "firstPlayDate": a.get("firstPlayDate"),
                        "playingDays": a.get("playingDays"),
                        "shopUri": a.get("shopUri"),
                        "hasUgc": a.get("hasUgc"),
                    }
                    for a in s.get("playedApps", [])
                ],
            }
            for s in device.daily_summaries[:5]
        ]

        # Build per-app playtime from today's player data.
        # Use max() across players because Nintendo reports the same console
        # playtime identically for every player who was active simultaneously.
        app_times: dict[str, int] = {}
        if is_today:
            players = (
                today_summary.get("devicePlayers")  # legacy schema (Switch / Switch Lite)
                or today_summary.get("players")     # updated schema (Switch 2)
                or []
            )
            for player in players:
                apps_in_player = (
                    player.get("playedApps")     # legacy schema
                    or player.get("playedGames") # updated schema (Switch 2)
                    or []
                )
                for app_entry in apps_in_player:
                    app_id = (
                        app_entry.get("applicationId")
                        or (app_entry.get("meta") or {}).get("applicationId")
                    )
                    if app_id:
                        key = app_id.upper()
                        app_times[key] = max(
                            app_times.get(key, 0),
                            app_entry.get("playingTime", 0),
                        )

        # ``device.applications`` is a dict in newer pynintendoparental versions.
        applications = []
        apps = device.applications
        if isinstance(apps, dict):
            apps = apps.values()
        for app in apps:
            try:
                today_time = app_times.get(app.application_id.upper(), 0) if is_today else 0
                applications.append(
                    {
                        "name": app.name,
                        "application_id": app.application_id,
                        "image_url": app.image_url,
                        "today_time_played": today_time,
                        "playing_days": app.playing_days,
                        "first_played_date": (
                            app.first_played_date.strftime("%Y-%m-%d")
                            if app.first_played_date
                            else None
                        ),
                        "shop_url": app.shop_url,
                        "has_ugc": app.has_ugc,
                    }
                )
            except Exception:  # noqa: BLE001
                _LOGGER.debug(
                    "Failed to process application data for device %s",
                    device.device_id,
                    exc_info=True,
                )

        return {"daily": daily, "applications": applications}
    except Exception:  # noqa: BLE001
        _LOGGER.debug(
            "Failed to build daily attributes for device %s",
            device.device_id,
            exc_info=True,
        )
        return None


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
        attributes_fn=_build_daily_attributes,
    ),
    NintendoParentalControlsDeviceSensorEntityDescription(
        key=NintendoParentalControlsSensor.TIME_REMAINING,
        translation_key=NintendoParentalControlsSensor.TIME_REMAINING,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.today_time_remaining,
    ),
    NintendoParentalControlsDeviceSensorEntityDescription(
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
    entities: list[NintendoDevice] = []
    entities.extend(
        NintendoParentalControlsDeviceSensorEntity(entry.runtime_data, device, sensor)
        for device in entry.runtime_data.api.devices.values()
        for sensor in DEVICE_SENSOR_DESCRIPTIONS
    )
    for device in entry.runtime_data.api.devices.values():
        entities.extend(
            NintendoParentalControlsPlayerSensorEntity(
                entry.runtime_data, device, player_id, sensor
            )
            for player_id in device.players
            for sensor in PLAYER_SENSOR_DESCRIPTIONS
        )
    async_add_entities(entities)


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

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        return self.entity_description.attributes_fn(self._device)


class NintendoParentalControlsPlayerSensorEntity(NintendoDevice, SensorEntity):
    """Represent a single player sensor."""

    entity_description: NintendoParentalControlsPlayerSensorEntityDescription

    def __init__(
        self,
        coordinator: NintendoUpdateCoordinator,
        device: Device,
        player_id: str,
        description: NintendoParentalControlsPlayerSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator, device=device, key=description.key)
        self.entity_description = description
        self.player_id = player_id
        player_obj = device.get_player(player_id)
        nickname = player_obj.nickname or ""
        self._attr_translation_placeholders = {"nickname": nickname}
        self._attr_unique_id = f"{device.device_id}_{player_id}_{description.key}"

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture."""
        if self.player_id not in self._device.players:
            return None
        return self._device.get_player(self.player_id).player_image

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        if self.player_id not in self._device.players:
            return None
        return self.entity_description.value_fn(self._device.get_player(self.player_id))
