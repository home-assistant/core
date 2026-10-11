"""The Philips TV integration."""

import logging

from haphilipsjs import PhilipsTV
from haphilipsjs.typing import SystemType

from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import CONF_MENU_NODES, CONF_SYSTEM
from .coordinator import (
    PhilipsTVConfigEntry,
    PhilipsTVDataUpdateCoordinator,
    get_menu_store,
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.MEDIA_PLAYER,
    Platform.REMOTE,
    Platform.SWITCH,
]

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: PhilipsTVConfigEntry) -> bool:
    """Set up Philips TV from a config entry."""

    system: SystemType | None = entry.data.get(CONF_SYSTEM)
    tvapi = PhilipsTV(
        entry.data[CONF_HOST],
        entry.data[CONF_API_VERSION],
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
        system=system,
    )
    coordinator = PhilipsTVDataUpdateCoordinator(hass, entry, tvapi)

    await coordinator.async_config_entry_first_refresh()

    if (actual_system := tvapi.system) and actual_system != system:
        data = {**entry.data, CONF_SYSTEM: actual_system}
        hass.config_entries.async_update_entry(entry, data=data)

    entry.runtime_data = coordinator

    _async_remove_unselected_menu_entities(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_entry))

    return True


async def async_update_entry(hass: HomeAssistant, entry: PhilipsTVConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PhilipsTVConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: PhilipsTVConfigEntry) -> None:
    """Remove the cached menu structure of a config entry."""
    await get_menu_store(hass, entry.entry_id).async_remove()


@callback
def _async_remove_unselected_menu_entities(
    hass: HomeAssistant,
    entry: PhilipsTVConfigEntry,
    coordinator: PhilipsTVDataUpdateCoordinator,
) -> None:
    """Remove entities of menu settings that are no longer selected."""
    prefix = f"{coordinator.unique_id}_menu_"

    def _parse_unique_id(unique_id: str) -> tuple[int, str | None] | None:
        """Return node id and slider id of a menu entity unique id."""
        if not unique_id.startswith(prefix):
            return None
        node_id, _, slider_id = unique_id.removeprefix(prefix).partition("_")
        return int(node_id), slider_id or None

    selected = set(entry.options.get(CONF_MENU_NODES, []))
    entity_registry = er.async_get(hass)
    unselected = [
        entity.entity_id
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if (parsed := _parse_unique_id(entity.unique_id)) and parsed[0] not in selected
    ]
    for entity_id in unselected:
        entity_registry.async_remove(entity_id)
