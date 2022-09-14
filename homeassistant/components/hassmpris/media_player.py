"""Support for interfacing with the HASS MPRIS agent."""
from __future__ import annotations

from typing import cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER as _LOGGER
from .media_player_entity_manager import EntityManager
from .models import HassmprisData

PLATFORM = "media_player"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all the media players for the MPRIS integration."""
    component_data = cast(
        HassmprisData,
        hass.data[DOMAIN][config_entry.entry_id],
    )
    mpris_client = component_data.client
    manager = EntityManager(
        hass,
        config_entry,
        mpris_client,
        async_add_entities,
    )
    await manager.start()
    component_data.entity_manager = manager

    async def _async_stop_manager(*unused_args):
        # The following is a very simple trick to delete the
        # reference to the manager once the manager is stopped
        # once via this mechanism.
        # That way, if the manager is stopped because the entry
        # was unloaded (e.g. integration deleted), this will
        # not try to stop the manager again.
        if component_data.entity_manager:
            _LOGGER.debug("Stopping entity manager")
            await component_data.entity_manager.stop()
            _LOGGER.debug("Entity manager stopped")
            component_data.entity_manager = None

    component_data.unloaders.append(_async_stop_manager)
