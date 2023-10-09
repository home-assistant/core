import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import (ButtonEntity,
                                             ButtonEntityDescription)
from homeassistant.exceptions import HomeAssistantError
from pytedee_async import TedeeClient, TedeeClientException

from .const import DOMAIN
from .entity import TedeeEntity, TedeeEntityDescription

_LOGGER = logging.getLogger(__name__)

@dataclass
class TedeeButtonEntityDescriptionMixin:
    """Mixin functions for Tedee button entity description."""
    press_fn: Callable[[TedeeClient, str], Coroutine[Any, Any, None]]


@dataclass
class TedeeButtonEntityDescription(
        ButtonEntityDescription,
        TedeeEntityDescription,
        TedeeButtonEntityDescriptionMixin
    ):
    """Describes Tedee button entity."""


BUTTONS: tuple[TedeeButtonEntityDescription, ...] = (
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
    )
)

async def async_setup_entry(hass, entry, async_add_entities):
    
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for lock in coordinator.data.values():
        if lock.is_enabled_pullspring:
            for button in BUTTONS:
                entities.append(TedeeButtonEntity(button, lock, coordinator))

    async_add_entities(entities)


class TedeeButtonEntity(TedeeEntity, ButtonEntity):
    """Button to only pull the spring (does not unlock if locked)"""
    def __init__(self, entity_description, lock, coordinator):
        _LOGGER.debug("Setting up ButtonEntity for %s", lock.name)
        super().__init__(lock, coordinator, entity_description)
        

    async def async_press(self, **kwargs) -> None:
        try:
            self._lock.state = 4
            self.async_write_ha_state()
            await self.entity_description.press_fn(self.coordinator._tedee_client, self._lock.id)
            await self.coordinator.async_request_refresh()
        except (TedeeClientException, Exception) as ex:
            _LOGGER.debug("Error while unlatching the door through button: %s", ex)
            raise HomeAssistantError(ex) from ex