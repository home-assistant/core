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

from .const import (
    ACCOUNT_FOLLOWERS_COUNT,
    ACCOUNT_FOLLOWING_COUNT,
    ACCOUNT_STATUSES_COUNT,
)
from .coordinator import MastodonConfigEntry, MastodonCoordinator
from .entity import MastodonEntity


@dataclass(frozen=True, kw_only=True)
class MastodonSensorEntityDescription(SensorEntityDescription):
    """Describes Mastodon sensor entity."""

    value_fn: Callable[[dict[str, Any]], StateType]


ENTITY_DESCRIPTIONS = (
    MastodonSensorEntityDescription(
        key="followers",
        native_unit_of_measurement="followers",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get(ACCOUNT_FOLLOWERS_COUNT),
    ),
    MastodonSensorEntityDescription(
        key="following",
        native_unit_of_measurement="accounts",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get(ACCOUNT_FOLLOWING_COUNT),
    ),
    MastodonSensorEntityDescription(
        key="statuses",
        native_unit_of_measurement="statuses",
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
            entity_description=entity_description,
            coordinator=coordinator,
            data=entry,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class MastodonSensorEntity(MastodonEntity, SensorEntity):
    """A sensor entity."""

    entity_description: MastodonSensorEntityDescription

    def __init__(
        self,
        coordinator: MastodonCoordinator,
        entity_description: MastodonSensorEntityDescription,
        data: MastodonConfigEntry,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator, entity_description, data)
        self.entity_description = entity_description
        self._attr_translation_key = entity_description.key

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
