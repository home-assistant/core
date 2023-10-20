"""Button entity for Tedee locks."""
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from pytedee_async import TedeeClient, TedeeClientException

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import TedeeEntity, TedeeEntityDescription


@dataclass
class TedeeButtonEntityDescriptionMixin:
    """Mixin functions for Tedee button entity description."""

    press_fn: Callable[[TedeeClient, str], Coroutine[Any, Any, None]]


@dataclass
class TedeeButtonEntityDescription(
    ButtonEntityDescription, TedeeEntityDescription, TedeeButtonEntityDescriptionMixin
):
    """Describes Tedee button entity."""


ENTITIES: tuple[TedeeButtonEntityDescription, ...] = (
    TedeeButtonEntityDescription(
        key="unlatch",
        translation_key="unlatch",
        icon="mdi:gesture-tap-button",
        unique_id_fn=lambda lock: f"{lock.lock_id}-unlatch-button",
        press_fn=lambda client, lock_id: client.pull(lock_id),
    ),
    TedeeButtonEntityDescription(
        key="unlock_unlatch",
        translation_key="unlock_unlatch",
        icon="mdi:gesture-tap-button",
        unique_id_fn=lambda lock: f"{lock.lock_id}-unlockunlatch-button",
        press_fn=lambda client, lock_id: client.open(lock_id),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tedee button entity."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for lock in coordinator.data.values():
        if bool(lock.is_enabled_pullspring):
            for entity_description in ENTITIES:
                entities.append(
                    TedeeButtonEntity(lock, coordinator, entity_description)
                )

    async_add_entities(entities)


class TedeeButtonEntity(TedeeEntity, ButtonEntity):
    """Button to only pull the spring (does not unlock if locked)."""

    entity_description: TedeeButtonEntityDescription

    async def async_press(self, **kwargs) -> None:
        """Press the button."""
        try:
            self._lock.state = 4
            self.async_write_ha_state()
            await self.entity_description.press_fn(
                self.coordinator.tedee_client, self._lock.lock_id
            )
            await self.coordinator.async_request_refresh()
        except (TedeeClientException, Exception) as ex:
            raise HomeAssistantError(
                "Error while unlatching the lock {} through button: {}".format(
                    str(self._lock.lock_id), ex
                )
            ) from ex
