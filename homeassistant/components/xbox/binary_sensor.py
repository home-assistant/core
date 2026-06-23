"""Xbox friends binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, override

from pythonxbox.api.provider.people.models import Person
from pythonxbox.api.provider.titlehub.models import Title

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import XboxConfigEntry
from .entity import XboxBaseEntity, XboxBaseEntityDescription, profile_pic

PARALLEL_UPDATES = 0


class XboxBinarySensor(StrEnum):
    """Xbox binary sensor."""

    ONLINE = "online"
    IN_GAME = "in_game"
    HAS_GAME_PASS = "has_game_pass"


@dataclass(kw_only=True, frozen=True)
class XboxBinarySensorEntityDescription(
    XboxBaseEntityDescription, BinarySensorEntityDescription
):
    """Xbox binary sensor description."""

    is_on_fn: Callable[[Person], bool | None]


def profile_attributes(person: Person, _: Title | None) -> dict[str, Any]:
    """Attributes for the profile."""
    attributes: dict[str, Any] = {}
    attributes["display_name"] = person.display_name
    attributes["real_name"] = person.real_name or None
    attributes["bio"] = person.detail.bio if person.detail else None
    attributes["location"] = person.detail.location if person.detail else None
    return attributes


def in_game(person: Person) -> bool:
    """True if person is in a game."""

    active_app = (
        next(
            (presence for presence in person.presence_details if presence.is_primary),
            None,
        )
        if person.presence_details
        else None
    )
    return (
        active_app is not None and active_app.is_game and active_app.state == "Active"
    )


SENSOR_DESCRIPTIONS: tuple[XboxBinarySensorEntityDescription, ...] = (
    XboxBinarySensorEntityDescription(
        key=XboxBinarySensor.ONLINE,
        translation_key=XboxBinarySensor.ONLINE,
        is_on_fn=lambda x: x.presence_state == "Online",
        name=None,
        entity_picture_fn=profile_pic,
        attributes_fn=profile_attributes,
    ),
    XboxBinarySensorEntityDescription(
        key=XboxBinarySensor.IN_GAME,
        translation_key=XboxBinarySensor.IN_GAME,
        is_on_fn=in_game,
    ),
    XboxBinarySensorEntityDescription(
        key=XboxBinarySensor.HAS_GAME_PASS,
        translation_key=XboxBinarySensor.HAS_GAME_PASS,
        is_on_fn=lambda x: x.detail.has_game_pass if x.detail else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Xbox Live friends."""
    coordinator = entry.runtime_data.presence

    if TYPE_CHECKING:
        assert entry.unique_id
    async_add_entities(
        [
            XboxBinarySensorEntity(coordinator, entry.unique_id, description)
            for description in SENSOR_DESCRIPTIONS
        ]
    )

    for subentry_id, subentry in entry.subentries.items():
        async_add_entities(
            [
                XboxBinarySensorEntity(coordinator, subentry.unique_id, description)
                for description in SENSOR_DESCRIPTIONS
                if subentry.unique_id
                and subentry.unique_id in coordinator.data.presence
                and subentry.subentry_type == "friend"
            ],
            config_subentry_id=subentry_id,
        )


class XboxBinarySensorEntity(XboxBaseEntity, BinarySensorEntity):
    """Representation of a Xbox presence state."""

    entity_description: XboxBinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the status of the requested attribute."""

        return self.entity_description.is_on_fn(self.data)
