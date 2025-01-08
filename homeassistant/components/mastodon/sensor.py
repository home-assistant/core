"""Mastodon platform for sensor components."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import MastodonConfigEntry
from .const import (
    ACCOUNT_FOLLOWERS_COUNT,
    ACCOUNT_FOLLOWING_COUNT,
    ACCOUNT_STATUSES_COUNT,
)
from .entity import MastodonEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MastodonSensorEntityDescription(SensorEntityDescription):
    """Describes Mastodon sensor entity."""

    value_fn: Callable[[dict[str, Any]], StateType]


ENTITY_DESCRIPTIONS = (
    MastodonSensorEntityDescription(
        key="followers",
        translation_key="followers",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get(ACCOUNT_FOLLOWERS_COUNT),
    ),
    MastodonSensorEntityDescription(
        key="following",
        translation_key="following",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get(ACCOUNT_FOLLOWING_COUNT),
    ),
    MastodonSensorEntityDescription(
        key="posts",
        translation_key="posts",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get(ACCOUNT_STATUSES_COUNT),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MastodonConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
