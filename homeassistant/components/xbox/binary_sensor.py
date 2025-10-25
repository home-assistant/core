"""Xbox friends binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from functools import partial

from xbox.webapi.api.provider.people.models import Person
from yarl import URL

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import XboxConfigEntry, XboxUpdateCoordinator
from .entity import XboxBaseEntity, check_deprecated_entity


class XboxBinarySensor(StrEnum):
    """Xbox binary sensor."""

    ONLINE = "online"
    IN_PARTY = "in_party"
    IN_GAME = "in_game"
    IN_MULTIPLAYER = "in_multiplayer"
    HAS_GAME_PASS = "has_game_pass"


@dataclass(kw_only=True, frozen=True)
class XboxBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Xbox binary sensor description."""

    is_on_fn: Callable[[Person], bool | None]
    entity_picture_fn: Callable[[Person], str | None] | None = None
    deprecated: bool | None = None


def profile_pic(person: Person) -> str | None:
    """Return the gamer pic."""

    # Xbox sometimes returns a domain that uses a wrong certificate which
    # creates issues with loading the image.
    # The correct domain is images-eds-ssl which can just be replaced
    # to point to the correct image, with the correct domain and certificate.
    # We need to also remove the 'mode=Padding' query because with it,
    # it results in an error 400.
    url = URL(person.display_pic_raw)
    if url.host == "images-eds.xboxlive.com":
        url = url.with_host("images-eds-ssl.xboxlive.com").with_scheme("https")
    query = dict(url.query)
    query.pop("mode", None)
    return str(url.with_query(query))


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
    ),
    XboxBinarySensorEntityDescription(
        key=XboxBinarySensor.IN_PARTY,
        translation_key=XboxBinarySensor.IN_PARTY,
        is_on_fn=(
            lambda x: bool(x.multiplayer_summary.in_party)
            if x.multiplayer_summary
            else None
        ),
        entity_registry_enabled_default=False,
        deprecated=True,
    ),
    XboxBinarySensorEntityDescription(
        key=XboxBinarySensor.IN_GAME,
        translation_key=XboxBinarySensor.IN_GAME,
        is_on_fn=in_game,
    ),
    XboxBinarySensorEntityDescription(
        key=XboxBinarySensor.IN_MULTIPLAYER,
        translation_key=XboxBinarySensor.IN_MULTIPLAYER,
        is_on_fn=(
            lambda x: bool(x.multiplayer_summary.in_multiplayer_session)
            if x.multiplayer_summary
            else None
        ),
        entity_registry_enabled_default=False,
        deprecated=True,
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
    coordinator = entry.runtime_data

    update_friends = partial(
        async_update_friends, hass, coordinator, {}, async_add_entities
    )

    entry.async_on_unload(coordinator.async_add_listener(update_friends))

    update_friends()


class XboxBinarySensorEntity(XboxBaseEntity, BinarySensorEntity):
    """Representation of a Xbox presence state."""

    entity_description: XboxBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return the status of the requested attribute."""

        return self.entity_description.is_on_fn(self.data)

    @property
    def entity_picture(self) -> str | None:
        """Return the gamer pic."""

        return (
            fn(self.data)
            if (fn := self.entity_description.entity_picture_fn) is not None
            else super().entity_picture
        )


@callback
def async_update_friends(
    hass: HomeAssistant,
    coordinator: XboxUpdateCoordinator,
    current: dict[str, list[XboxBinarySensorEntity]],
    async_add_entities,
) -> None:
    """Update friends."""
    new_ids = set(coordinator.data.presence)
    current_ids = set(current)

    # Process new favorites, add them to Home Assistant
    new_entities: list[XboxBinarySensorEntity] = []
    for xuid in new_ids - current_ids:
        current[xuid] = []
        for description in SENSOR_DESCRIPTIONS:
            entity = XboxBinarySensorEntity(coordinator, xuid, description)
            if check_deprecated_entity(hass, entity, BINARY_SENSOR_DOMAIN):
                current[xuid].append(entity)
        new_entities = new_entities + current[xuid]
    if new_entities:
        async_add_entities(new_entities)

    # Process deleted favorites, remove them from Home Assistant
    for xuid in current_ids - new_ids:
        del current[xuid]
