"""Sensor platform for the Xbox integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from xbox.webapi.api.provider.people.models import Person

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
from .entity import XboxBaseEntity, check_deprecated_entity


class XboxSensor(StrEnum):
    """Xbox sensor."""

    STATUS = "status"
    GAMER_SCORE = "gamer_score"
    ACCOUNT_TIER = "account_tier"
    GOLD_TENURE = "gold_tenure"
    LAST_ONLINE = "last_online"
    FOLLOWING = "following"
    FOLLOWER = "follower"


@dataclass(kw_only=True, frozen=True)
class XboxSensorEntityDescription(SensorEntityDescription):
    """Xbox sensor description."""

    value_fn: Callable[[Person], StateType | datetime]
    deprecated: bool | None = None


SENSOR_DESCRIPTIONS: tuple[XboxSensorEntityDescription, ...] = (
    XboxSensorEntityDescription(
        key=XboxSensor.STATUS,
        translation_key=XboxSensor.STATUS,
        value_fn=lambda x: x.presence_text,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.GAMER_SCORE,
        translation_key=XboxSensor.GAMER_SCORE,
        value_fn=lambda x: x.gamer_score,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.ACCOUNT_TIER,
        value_fn=lambda _: None,
        deprecated=True,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.GOLD_TENURE,
        value_fn=lambda _: None,
        deprecated=True,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.LAST_ONLINE,
        translation_key=XboxSensor.LAST_ONLINE,
        value_fn=(
            lambda x: x.last_seen_date_time_utc.replace(tzinfo=UTC)
            if x.last_seen_date_time_utc
            else None
        ),
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.FOLLOWING,
        translation_key=XboxSensor.FOLLOWING,
        value_fn=lambda x: x.detail.following_count if x.detail else None,
    ),
    XboxSensorEntityDescription(
        key=XboxSensor.FOLLOWER,
        translation_key=XboxSensor.FOLLOWER,
        value_fn=lambda x: x.detail.follower_count if x.detail else None,
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
            async_add_entities(
                [
                    XboxSensorEntity(coordinator, xuid, description)
                    for xuid in new_xuids
                    for description in SENSOR_DESCRIPTIONS
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
        return self.entity_description.value_fn(self.data)
