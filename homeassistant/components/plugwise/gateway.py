"""Plugwise platform for Home Assistant Core."""
from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import ClientConnectionError
from plugwise.exceptions import InvalidAuthentication, PlugwiseException
from plugwise.smile import Smile

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DOMAIN,
    LOGGER,
    PLATFORMS_GATEWAY,
    Platform,
)
from .coordinator import PlugwiseDataUpdateCoordinator


async def async_setup_entry_gw(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Plugwise Smiles from a config entry."""
    await er.async_migrate_entries(hass, entry.entry_id, async_migrate_entity_entry)

    websession = async_get_clientsession(hass, verify_ssl=False)
    api = Smile(
        host=entry.data[CONF_HOST],
        username=entry.data.get(CONF_USERNAME, DEFAULT_USERNAME),
        password=entry.data[CONF_PASSWORD],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        timeout=30,
        websession=websession,
    )

    try:
        connected = await api.connect()
    except InvalidAuthentication:
        LOGGER.error("Invalid username or Smile ID")
        return False
    except (ClientConnectionError, PlugwiseException) as err:
        raise ConfigEntryNotReady(
            f"Error while communicating to device {api.smile_name}"
        ) from err
    except asyncio.TimeoutError as err:
        raise ConfigEntryNotReady(
            f"Timeout while connecting to Smile {api.smile_name}"
        ) from err

    if not connected:
        raise ConfigEntryNotReady("Unable to connect to Smile")
    api.get_all_devices()

    if entry.unique_id is None and api.smile_version[0] != "1.8.0":
        hass.config_entries.async_update_entry(entry, unique_id=api.smile_hostname)

    coordinator = PlugwiseDataUpdateCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()
    migrate_sensor_entities(hass, coordinator)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, str(api.gateway_id))},
        manufacturer="Plugwise",
        name=entry.title,
        model=f"Smile {api.smile_name}",
        sw_version=api.smile_version[0],
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS_GATEWAY)

    return True


async def async_unload_entry_gw(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS_GATEWAY
    ):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


@callback
def async_migrate_entity_entry(entry: er.RegistryEntry) -> dict[str, Any] | None:
    """Migrate Plugwise entity entries.

    - Migrates unique ID from old relay switches to the new unique ID
    """
    if entry.domain == Platform.SWITCH and entry.unique_id.endswith("-plug"):
        return {"new_unique_id": entry.unique_id.replace("-plug", "-relay")}

    # No migration needed
    return None


def migrate_sensor_entities(
    hass: HomeAssistant,
    coordinator: PlugwiseDataUpdateCoordinator,
) -> None:
    """Migrate Sensors if needed."""
    ent_reg = er.async_get(hass)

    # Migrating opentherm_outdoor_temperature to opentherm_outdoor_air_temperature sensor
    for device_id, device in coordinator.data.devices.items():
        if device.get("dev_class") != "heater_central":
            continue

        old_unique_id = f"{device_id}-outdoor_temperature"
        if entity_id := ent_reg.async_get_entity_id(
            Platform.SENSOR, DOMAIN, old_unique_id
        ):
            new_unique_id = f"{device_id}-outdoor_air_temperature"
            LOGGER.debug(
                "Migrating entity %s from old unique ID '%s' to new unique ID '%s'",
                entity_id,
                old_unique_id,
                new_unique_id,
            )
            ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)
