"""Button entity for Tedee locks."""
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from pytedee_async import TedeeClient, TedeeClientException

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import TedeeEntity, TedeeEntityDescription

_LOGGER = logging.getLogger(__name__)


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
        unique_id_fn=lambda lock_id: f"{lock_id}-unlatch-button",
        press_fn=lambda client, lock_id: client.pull(lock_id),
    ),
    TedeeButtonEntityDescription(
        key="unlock_unlatch",
        translation_key="unlock_unlatch",
        icon="mdi:gesture-tap-button",
        unique_id_fn=lambda lock_id: f"{lock_id}-unlockunlatch-button",
        press_fn=lambda client, lock_id: client.open(lock_id),
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Tedee button entity."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for lock in coordinator.data.values():
        if lock.is_enabled_pullspring:
            for entity_description in ENTITIES:
                entities.append(
                    TedeeButtonEntity(lock, coordinator, entity_description)
                )

    async_add_entities(entities)


class TedeeButtonEntity(TedeeEntity, ButtonEntity):
    """Button to only pull the spring (does not unlock if locked)."""

    def __init__(self, lock, coordinator, entity_description):
        """Initialize the button."""
        _LOGGER.debug("Setting up ButtonEntity for %s", lock.name)
        super().__init__(lock, coordinator, entity_description)

    async def async_press(self, **kwargs) -> None:
        """Press the button."""
        try:
            self._lock.state = 4
            self.async_write_ha_state()
            await self.entity_description.press_fn(  # type: ignore[attr-defined]
                self.coordinator.tedee_client, self._lock.id
            )
            await self.coordinator.async_request_refresh()
        except (TedeeClientException, Exception) as ex:
            _LOGGER.debug("Error while unlatching the door through button: %s", ex)
            raise HomeAssistantError(ex) from ex
