"""Mastodon platform for sensor components."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from mastodon.Mastodon import Account, Instance, InstanceV2

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .coordinator import MastodonConfigEntry
from .entity import MastodonEntity
from .utils import construct_mastodon_username

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MastodonSensorEntityDescription(SensorEntityDescription):
    """Describes Mastodon sensor entity."""

    value_fn: Callable[[Account, InstanceV2 | Instance], StateType | datetime]
    attributes_fn: Callable[[Account], Mapping[str, Any]] | None = None
    entity_picture_fn: Callable[[Account], str] | None = None


def account_meta(data: Account) -> Mapping[str, Any]:
    """Account attributes."""

    return {
        "display_name": data.display_name,
        "bio": data.note,
        "created": dt_util.as_local(data.created_at).date(),
    }


ENTITY_DESCRIPTIONS = (
    MastodonSensorEntityDescription(
        key="followers",
        translation_key="followers",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data, _: data.followers_count,
    ),
    MastodonSensorEntityDescription(
        key="following",
        translation_key="following",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data, _: data.following_count,
    ),
    MastodonSensorEntityDescription(
        key="posts",
        translation_key="posts",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data, _: data.statuses_count,
    ),
    MastodonSensorEntityDescription(
        key="last_post",
        translation_key="last_post",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=(
            lambda data, _: (
                dt_util.as_local(data.last_status_at) if data.last_status_at else None
            )
        ),
    ),
    MastodonSensorEntityDescription(
        key="username",
        translation_key="username",
        value_fn=lambda data, instance: construct_mastodon_username(instance, data),
        attributes_fn=account_meta,
        entity_picture_fn=lambda data: data.avatar,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MastodonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform for entity."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        MastodonSensorEntity(
            coordinator=coordinator,
            entity_description=entity_description,
            data=entry,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class MastodonSensorEntity(MastodonEntity, SensorEntity):
    """A Mastodon sensor entity."""

    entity_description: MastodonSensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime:
        """Return the native value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data, self.instance)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes."""
        return (
            fn(self.coordinator.data)
            if (fn := self.entity_description.attributes_fn)
            else super().extra_state_attributes
        )

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""
        return (
            fn(self.coordinator.data)
            if (fn := self.entity_description.entity_picture_fn)
            else super().entity_picture
        )
