"""Mastodon platform for sensor components."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ACCOUNT_FOLLOWERS_COUNT,
    ACCOUNT_FOLLOWING_COUNT,
    ACCOUNT_STATUSES_COUNT,
)
from .coordinator import MastodonConfigEntry, MastodonCoordinator
from .entity import MastodonEntity

ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        key=ACCOUNT_FOLLOWERS_COUNT,
        translation_key="followers_count",
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key=ACCOUNT_FOLLOWING_COUNT,
        translation_key="following_count",
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key=ACCOUNT_STATUSES_COUNT,
        translation_key="statuses_count",
        state_class=SensorStateClass.TOTAL,
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
            data=entry,
            coordinator=coordinator,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class MastodonSensorEntity(MastodonEntity, SensorEntity):
    """A sensor entity."""

    def __init__(
        self,
        coordinator: MastodonCoordinator,
        entity_description: SensorEntityDescription,
        data: MastodonConfigEntry,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator, entity_description, data)

    @property
    def native_value(self) -> str | None:
        """Return the native value of the sensor."""
        return self.coordinator.data.get(self.entity_description.key)
