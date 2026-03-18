"""Binary sensor platform for Habitica integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from habiticalib import ContentData, UserData

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HABITICA_KEY
from .const import ASSETS_URL
from .coordinator import HabiticaConfigEntry, HabiticaPartyCoordinator
from .entity import HabiticaBase, HabiticaPartyBase

PARALLEL_UPDATES = 1


@dataclass(kw_only=True, frozen=True)
class HabiticaBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Habitica Binary Sensor Description."""

    value_fn: Callable[[UserData], bool | None]
    entity_picture: Callable[[UserData], str | None]


class HabiticaBinarySensor(StrEnum):
    """Habitica Entities."""

    PENDING_QUEST = "pending_quest"
    QUEST_RUNNING = "quest_running"


def get_scroll_image_for_pending_quest_invitation(user: UserData) -> str | None:
    """Entity picture for pending quest invitation."""
    if user.party.quest.key and user.party.quest.RSVPNeeded:
        return f"inventory_quest_scroll_{user.party.quest.key}.png"
    return None


BINARY_SENSOR_DESCRIPTIONS: tuple[HabiticaBinarySensorEntityDescription, ...] = (
    HabiticaBinarySensorEntityDescription(
        key=HabiticaBinarySensor.PENDING_QUEST,
        translation_key=HabiticaBinarySensor.PENDING_QUEST,
        value_fn=lambda user: user.party.quest.RSVPNeeded,
        entity_picture=get_scroll_image_for_pending_quest_invitation,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HabiticaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the habitica binary sensors."""

    coordinator = config_entry.runtime_data

    entities: list[BinarySensorEntity] = [
        HabiticaBinarySensorEntity(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]

    if party := coordinator.data.user.party.id:
        party_coordinator = hass.data[HABITICA_KEY][party]
        entities.append(
            HabiticaPartyBinarySensorEntity(
                party_coordinator,
                config_entry,
                coordinator.content,
            )
        )
    async_add_entities(entities)


class HabiticaBinarySensorEntity(HabiticaBase, BinarySensorEntity):
    """Representation of a Habitica binary sensor."""

    entity_description: HabiticaBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """If the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator.data.user)

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""
        if entity_picture := self.entity_description.entity_picture(
            self.coordinator.data.user
        ):
            return f"{ASSETS_URL}{entity_picture}"
        return None


class HabiticaPartyBinarySensorEntity(HabiticaPartyBase, BinarySensorEntity):
    """Representation of a Habitica party binary sensor."""

    entity_description = BinarySensorEntityDescription(
        key=HabiticaBinarySensor.QUEST_RUNNING,
        translation_key=HabiticaBinarySensor.QUEST_RUNNING,
    )

    def __init__(
        self,
        coordinator: HabiticaPartyCoordinator,
        config_entry: HabiticaConfigEntry,
        content: ContentData,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, config_entry, self.entity_description, content)

    @property
    def is_on(self) -> bool | None:
        """If the binary sensor is on."""
        return self.coordinator.data.party.quest.active
