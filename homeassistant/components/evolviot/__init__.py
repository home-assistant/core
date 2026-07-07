"""EvolvIOT Home Assistant integration."""

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EvolvIOTApi, normalize_api_base_url
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_API_BASE_URL,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_REFRESH_TOKEN,
    CONF_VERIFY_SSL,
    DATA_API,
    DATA_COORDINATOR,
    DATA_KNOWN_ENTITIES,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import EvolvIOTDataUpdateCoordinator, evolviot_entity_domain


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EvolvIOT from a config entry."""

    async def async_token_updated(token_data: dict[str, Any]) -> None:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_ACCESS_TOKEN: token_data[CONF_ACCESS_TOKEN],
                CONF_REFRESH_TOKEN: token_data.get(CONF_REFRESH_TOKEN, ""),
            },
        )

    verify_ssl = bool(entry.data.get(CONF_VERIFY_SSL, True))
    session = async_get_clientsession(hass, verify_ssl=verify_ssl)
    api = EvolvIOTApi(
        session,
        normalize_api_base_url(entry.data[CONF_API_BASE_URL]),
        entry.data[CONF_ACCESS_TOKEN],
        refresh_token=entry.data.get(CONF_REFRESH_TOKEN),
        client_id=entry.data.get(CONF_CLIENT_ID),
        client_secret=entry.data.get(CONF_CLIENT_SECRET),
        verify_ssl=verify_ssl,
        token_update_callback=async_token_updated,
    )
    coordinator = EvolvIOTDataUpdateCoordinator(hass, api, entry.entry_id)
    await coordinator.async_load_cache()
    await coordinator.async_config_entry_first_refresh()
    _remove_stale_entity_registry_entries(hass, coordinator)

    runtime_data = {
        DATA_API: api,
        DATA_COORDINATOR: coordinator,
        DATA_KNOWN_ENTITIES: {},
    }
    entry.runtime_data = runtime_data
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload EvolvIOT config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


def _remove_stale_entity_registry_entries(
    hass: HomeAssistant,
    coordinator: EvolvIOTDataUpdateCoordinator,
) -> None:
    """Remove old entities whose EvolvIOT control type changed domains."""
    entity_registry = er.async_get(hass)

    for entity in coordinator.entities.values():
        unique_id = entity.get("unique_id")
        if not unique_id:
            continue

        current_platform = _platform_for_evolviot_domain(evolviot_entity_domain(entity))
        for platform in PLATFORMS:
            if platform == current_platform:
                continue
            if entity_id := entity_registry.async_get_entity_id(
                platform,
                DOMAIN,
                str(unique_id),
            ):
                entity_registry.async_remove(entity_id)


def _platform_for_evolviot_domain(domain: str) -> Platform | str:
    """Return the HA platform that hosts an EvolvIOT effective domain."""
    if domain == "color":
        return Platform.LIGHT
    return domain
