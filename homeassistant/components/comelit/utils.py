"""Utils for Comelit."""

from typing import Any

from aiocomelit import ComelitSerialBridgeObject
from aiohttp import ClientSession, CookieJar

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    aiohttp_client,
    device_registry as dr,
    entity_registry as er,
)

from .const import _LOGGER


async def async_client_session(hass: HomeAssistant) -> ClientSession:
    """Return a new aiohttp session."""
    return aiohttp_client.async_create_clientsession(
        hass, verify_ssl=False, cookie_jar=CookieJar(unsafe=True)
    )


def load_api_data(device: ComelitSerialBridgeObject, domain: str) -> dict[Any, Any]:
    """Load data from the API."""
    # This function is called when the data is loaded from the API
    if not isinstance(device.val, list):
        raise HomeAssistantError(
            translation_domain=domain, translation_key="invalid_clima_data"
        )
    # CLIMATE has a 2 item tuple:
    # - first  for Clima
    # - second for Humidifier
    return device.val[0] if domain == CLIMATE_DOMAIN else device.val[1]


async def cleanup_stale_entity(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_index: int,
    device_domain: str,
    device_class: str | None = None,
) -> None:
    """Cleanup stale entity."""
    entity_reg: er.EntityRegistry = er.async_get(hass)

    entities_removed: bool = False

    for entry in er.async_entries_for_config_entry(entity_reg, config_entry.entry_id):
        if entry.domain != device_domain:
            # Only remove entities for specified domain
            continue

        if device_class:
            entry_unique_id = f"{config_entry.entry_id}-{device_index}-{device_class}"
        else:
            entry_unique_id = f"{config_entry.entry_id}-{device_index}"

        if entry.unique_id == entry_unique_id:
            entry_name = entry.name or entry.original_name
            _LOGGER.info("Removing entity: %s", entry_name)
            entity_reg.async_remove(entry.entity_id)
            entities_removed = True

    if entities_removed:
        _async_remove_empty_devices(hass, entity_reg, config_entry)


def _async_remove_empty_devices(
    hass: HomeAssistant, entity_reg: er.EntityRegistry, config_entry: ConfigEntry
) -> None:
    """Remove devices with no entities."""

    device_reg = dr.async_get(hass)
    device_list = dr.async_entries_for_config_entry(device_reg, config_entry.entry_id)
    for device_entry in device_list:
        if not er.async_entries_for_device(
            entity_reg,
            device_entry.id,
            include_disabled_entities=True,
        ):
            _LOGGER.info("Removing device: %s", device_entry.name)
            device_reg.async_remove_device(device_entry.id)
