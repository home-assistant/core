"""Sensor for Steam account status."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from time import mktime

from steam.user import profile

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utc_from_timestamp as utc

from . import SteamEntity
from .const import (
    CONF_ACCOUNTS,
    DOMAIN,
    STEAM_API_URL,
    STEAM_HEADER_IMAGE_FILE,
    STEAM_ICON_URL,
    STEAM_MAIN_IMAGE_FILE,
    STEAM_STATUSES,
)
from .coordinator import SteamDataUpdateCoordinator


def _get_game_icon(data: profile, icons: dict[int, str]) -> str | None:
    """Get game icon."""
    if (gid := data.current_game[0]) and (image_id := icons.get(gid)):
        return f"{STEAM_ICON_URL}{gid}/{image_id}.jpg"
    return None


@dataclass
class SteamSensorEntityMixin:
    """Mixin for Steam sensor."""

    value_fn: Callable[[profile], StateType | datetime]


@dataclass
class SteamSensorEntityDescription(SensorEntityDescription, SteamSensorEntityMixin):
    """Describes a Steam sensor."""

    entity_picture_fn: Callable[
        [profile, dict[int, str]], str | None
    ] = lambda val, _: None


SENSOR_TYPES: tuple[SteamSensorEntityDescription, ...] = (
    SteamSensorEntityDescription(
        key="state",
        name="State",
        icon="mdi:steam",
        value_fn=lambda data: STEAM_STATUSES[data.status],
        entity_picture_fn=lambda data, _: f"{STEAM_API_URL}{data.current_game[0]}/{STEAM_MAIN_IMAGE_FILE}"
        if data.current_game[0]
        else data.avatar_medium,
    ),
    SteamSensorEntityDescription(
        key="game",
        name="Game",
        icon="mdi:steam",
        value_fn=lambda data: data.current_game[2],
        entity_picture_fn=lambda data, _: f"{STEAM_API_URL}{data.current_game[0]}/{STEAM_HEADER_IMAGE_FILE}"
        if data.current_game[0]
        else None,
    ),
    SteamSensorEntityDescription(
        key="game_id",
        name="Game ID",
        icon="mdi:steam",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.current_game[0],
        entity_picture_fn=_get_game_icon,
    ),
    SteamSensorEntityDescription(
        key="last_online",
        name="Last online",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: utc(mktime(data.last_online)),
    ),
    SteamSensorEntityDescription(
        key="level",
        name="Level",
        icon="mdi:upload-multiple",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.level,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Steam platform."""
    coordinator: SteamDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SteamSensor(hass.data[DOMAIN][entry.entry_id], description, int(account))
        for description in SENSOR_TYPES
        for account in entry.options[CONF_ACCOUNTS]
        if int(account) in coordinator.data
    )


class SteamSensor(SteamEntity, SensorEntity):
    """A class for the Steam account."""

    entity_description: SteamSensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        account = self.coordinator.data.get(self._account)
        return self.entity_description.value_fn(account)

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""
        if (
            res := self.entity_description.entity_picture_fn(
                self.coordinator.data.get(self._account), self.coordinator.game_icons
            )
        ) is None:
            # Reset game icons to have coordinator get id for new game
            self.coordinator.game_icons = {}
        return res
