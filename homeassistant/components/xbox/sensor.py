"""Sensor platform for the Xbox integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from xbox.webapi.api.provider.people.models import Person
from xbox.webapi.api.provider.titlehub.models import Title

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import XboxConfigEntry
from .entity import XboxBaseEntity, XboxBaseEntityDescription, check_deprecated_entity


class XboxSensor(StrEnum):
    """Xbox sensor."""

    STATUS = "status"
    GAMER_SCORE = "gamer_score"
    ACCOUNT_TIER = "account_tier"
    GOLD_TENURE = "gold_tenure"
    LAST_ONLINE = "last_online"
    FOLLOWING = "following"
    FOLLOWER = "follower"
    NOW_PLAYING = "now_playing"


@dataclass(kw_only=True, frozen=True)
class XboxSensorEntityDescription(XboxBaseEntityDescription, SensorEntityDescription):
    """Xbox sensor description."""

    value_fn: Callable[[Person, Title | None], StateType | datetime]
    deprecated: bool | None = None


def now_playing_attributes(_: Person, title: Title | None) -> dict[str, Any]:
    """Attributes of the currently played title."""
    attributes: dict[str, Any] = {
        "short_description": None,
        "genres": None,
        "developer": None,
        "publisher": None,
        "release_date": None,
        "min_age": None,
        "achievements": None,
        "gamerscore": None,
        "progress": None,
    }
    if not title:
        return attributes
    if title.detail is not None:
        attributes.update(
            {
                "short_description": title.detail.short_description,
                "genres": (
                    ", ".join(title.detail.genres) if title.detail.genres else None
                ),
                "developer": title.detail.developer_name,
                "publisher": title.detail.publisher_name,
                "release_date": (
                    title.detail.release_date.replace(tzinfo=UTC).date()
                    if title.detail.release_date
                    else None
                ),
                "min_age": title.detail.min_age,
            }
        )
    if (achievement := title.achievement) is not None:
        attributes.update(
            {
                "achievements": (
                    f"{achievement.current_achievements} / {achievement.total_achievements}"
                ),
                "gamerscore": (
                    f"{achievement.current_gamerscore} / {achievement.total_gamerscore}"
                ),
                "progress": f"{int(achievement.progress_percentage)} %",
            }
        )

    return attributes


def title_logo(_: Person, title: Title | None) -> str | None:
    """Get the game logo."""

    return (
        next((i.url for i in title.images if i.type == "Tile"), None)
        or next((i.url for i in title.images if i.type == "Logo"), None)
        if title and title.images
        else None
    )


SENSOR_DESCRIPTIONS: tuple[XboxSensorEntityDescription, ...] = (
    XboxSensorEntityDescription(
        key=XboxSensor.STATUS,
        translation_key=XboxSensor.STATUS,
        value_fn=lambda x, _: x.presence_text,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.GAMER_SCORE,
        translation_key=XboxSensor.GAMER_SCORE,
        value_fn=lambda x, _: x.gamer_score,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.ACCOUNT_TIER,
        value_fn=lambda _, __: None,
        deprecated=True,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.GOLD_TENURE,
        value_fn=lambda _, __: None,
        deprecated=True,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.LAST_ONLINE,
        translation_key=XboxSensor.LAST_ONLINE,
        value_fn=(
            lambda x, _: x.last_seen_date_time_utc.replace(tzinfo=UTC)
            if x.last_seen_date_time_utc
            else None
        ),
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.FOLLOWING,
        translation_key=XboxSensor.FOLLOWING,
        value_fn=lambda x, _: x.detail.following_count if x.detail else None,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.FOLLOWER,
        translation_key=XboxSensor.FOLLOWER,
        value_fn=lambda x, _: x.detail.follower_count if x.detail else None,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.NOW_PLAYING,
        translation_key=XboxSensor.NOW_PLAYING,
        value_fn=lambda _, title: title.name if title else None,
        attributes_fn=now_playing_attributes,
        entity_picture_fn=title_logo,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: XboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Xbox Live friends."""
    xuids_added: set[str] = set()
    coordinator = config_entry.runtime_data

    @callback
    def add_entities() -> None:
        nonlocal xuids_added

        current_xuids = set(coordinator.data.presence)
        if new_xuids := current_xuids - xuids_added:
            for xuid in new_xuids:
                async_add_entities(
                    [
                        XboxSensorEntity(coordinator, xuid, description)
                        for description in SENSOR_DESCRIPTIONS
                        if check_deprecated_entity(
                            hass, xuid, description, SENSOR_DOMAIN
                        )
                    ]
                )
            xuids_added |= new_xuids
        xuids_added &= current_xuids

    coordinator.async_add_listener(add_entities)
    add_entities()


class XboxSensorEntity(XboxBaseEntity, SensorEntity):
    """Representation of a Xbox presence state."""

    entity_description: XboxSensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the requested attribute."""
        return self.entity_description.value_fn(self.data, self.title_info)
