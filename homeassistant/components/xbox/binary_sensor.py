"""Xbox friends binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from functools import partial

from yarl import URL

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PresenceData, XboxConfigEntry, XboxUpdateCoordinator
from .entity import XboxBaseEntity


class XboxBinarySensor(StrEnum):
    """Xbox binary sensor."""

    ONLINE = "online"
    IN_PARTY = "in_party"
    IN_GAME = "in_game"
    IN_MULTIPLAYER = "in_multiplayer"


@dataclass(kw_only=True, frozen=True)
class XboxBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Xbox binary sensor description."""

    is_on_fn: Callable[[PresenceData], bool | None]
    entity_picture_fn: Callable[[PresenceData], str | None] | None = None


def profile_pic(data: PresenceData) -> str | None:
    """Return the gamer pic."""

    # Xbox sometimes returns a domain that uses a wrong certificate which
    # creates issues with loading the image.
    # The correct domain is images-eds-ssl which can just be replaced
    # to point to the correct image, with the correct domain and certificate.
    # We need to also remove the 'mode=Padding' query because with it,
    # it results in an error 400.
    url = URL(data.display_pic)
    if url.host == "images-eds.xboxlive.com":
        url = url.with_host("images-eds-ssl.xboxlive.com").with_scheme("https")
    query = dict(url.query)
    query.pop("mode", None)
    return str(url.with_query(query))


SENSOR_DESCRIPTIONS: tuple[XboxBinarySensorEntityDescription, ...] = (
    XboxBinarySensorEntityDescription(
        key=XboxBinarySensor.ONLINE,
        translation_key=XboxBinarySensor.ONLINE,
        is_on_fn=lambda x: x.online,
        name=None,
        entity_picture_fn=profile_pic,
    ),
    XboxBinarySensorEntityDescription(
        key=XboxBinarySensor.IN_PARTY,
        translation_key=XboxBinarySensor.IN_PARTY,
        is_on_fn=lambda x: x.in_party,
        entity_registry_enabled_default=False,
    ),
    XboxBinarySensorEntityDescription(
        key=XboxBinarySensor.IN_GAME,
        translation_key=XboxBinarySensor.IN_GAME,
        is_on_fn=lambda x: x.in_game,
        entity_registry_enabled_default=False,
    ),
    XboxBinarySensorEntityDescription(
        key=XboxBinarySensor.IN_MULTIPLAYER,
        translation_key=XboxBinarySensor.IN_MULTIPLAYER,
        is_on_fn=lambda x: x.in_multiplayer,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Xbox Live friends."""
    coordinator = entry.runtime_data

    update_friends = partial(async_update_friends, coordinator, {}, async_add_entities)

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
        current[xuid] = [
            XboxBinarySensorEntity(coordinator, xuid, description)
            for description in SENSOR_DESCRIPTIONS
        ]
        new_entities = new_entities + current[xuid]
    if new_entities:
        async_add_entities(new_entities)

    # Process deleted favorites, remove them from Home Assistant
    for xuid in current_ids - new_ids:
        coordinator.hass.async_create_task(
            async_remove_entities(xuid, coordinator, current)
        )


async def async_remove_entities(
    xuid: str,
    coordinator: XboxUpdateCoordinator,
    current: dict[str, list[XboxBinarySensorEntity]],
) -> None:
    """Remove friend sensors from Home Assistant."""
    registry = er.async_get(coordinator.hass)
    entities = current[xuid]
    for entity in entities:
        if entity.entity_id in registry.entities:
            registry.async_remove(entity.entity_id)
    del current[xuid]
