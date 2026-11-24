"""BenQ Projector Infrared integration for Home Assistant."""

from homeassistant.components.infrared import async_get_emitters, async_get_receivers
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import entity_registry as er

from .const import CONF_INFRARED_ENTITY_ID, CONF_INFRARED_RECEIVER_ENTITY_ID, DOMAIN

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up BenQ Projector Infrared from a config entry."""
    entity_registry = er.async_get(hass)
    emitter_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
    if entity_registry.async_get(
        emitter_entity_id
    ) is None and emitter_entity_id not in async_get_emitters(hass):
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="emitter_not_found"
        )
    if (
        (receiver_entity_id := entry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID))
        and entity_registry.async_get(receiver_entity_id) is None
        and receiver_entity_id not in async_get_receivers(hass)
    ):
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="receiver_not_found"
        )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a BenQ Projector Infrared config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
