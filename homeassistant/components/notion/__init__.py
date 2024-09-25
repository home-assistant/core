"""Support for Notion."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from aionotion.errors import InvalidCredentialsError, NotionError
from aionotion.listener.models import ListenerKind

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_REFRESH_TOKEN,
    CONF_USER_UUID,
    DOMAIN,
    LOGGER,
    SENSOR_BATTERY,
    SENSOR_DOOR,
    SENSOR_GARAGE_DOOR,
    SENSOR_LEAK,
    SENSOR_MISSING,
    SENSOR_SAFE,
    SENSOR_SLIDING,
    SENSOR_SMOKE_CO,
    SENSOR_TEMPERATURE,
    SENSOR_WINDOW_HINGED,
)
from .coordinator import NotionDataUpdateCoordinator
from .util import async_get_client_with_credentials, async_get_client_with_refresh_token

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

ATTR_SYSTEM_MODE = "system_mode"
ATTR_SYSTEM_NAME = "system_name"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=1)


# Define a map of old-API task types to new-API listener types:
TASK_TYPE_TO_LISTENER_MAP: dict[str, ListenerKind] = {
    SENSOR_BATTERY: ListenerKind.BATTERY,
    SENSOR_DOOR: ListenerKind.DOOR,
    SENSOR_GARAGE_DOOR: ListenerKind.GARAGE_DOOR,
    SENSOR_LEAK: ListenerKind.LEAK_STATUS,
    SENSOR_MISSING: ListenerKind.CONNECTED,
    SENSOR_SAFE: ListenerKind.SAFE,
    SENSOR_SLIDING: ListenerKind.SLIDING_DOOR_OR_WINDOW,
    SENSOR_SMOKE_CO: ListenerKind.SMOKE,
    SENSOR_TEMPERATURE: ListenerKind.TEMPERATURE,
    SENSOR_WINDOW_HINGED: ListenerKind.HINGED_WINDOW,
}


@callback
def is_uuid(value: str) -> bool:
    """Return whether a string is a valid UUID."""
    try:
        UUID(value)
    except ValueError:
        return False
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Notion as a config entry."""
    entry_updates: dict[str, Any] = {"data": {**entry.data}}

    if not entry.unique_id:
        entry_updates["unique_id"] = entry.data[CONF_USERNAME]

    try:
        if password := entry_updates["data"].pop(CONF_PASSWORD, None):
            # If a password exists in the config entry data, use it to get a new client
            # (and pop it from the new entry data):
            client = await async_get_client_with_credentials(
                hass, entry.data[CONF_USERNAME], password
            )
        else:
            # If a password doesn't exist in the config entry data, we can safely assume
            # that a refresh token and user UUID do, so we use them to get the client:
            client = await async_get_client_with_refresh_token(
                hass,
                entry.data[CONF_USER_UUID],
                entry.data[CONF_REFRESH_TOKEN],
            )
    except InvalidCredentialsError as err:
        raise ConfigEntryAuthFailed("Invalid credentials") from err
    except NotionError as err:
        raise ConfigEntryNotReady("Config entry failed to load") from err

    # Update the Notion user UUID and refresh token if they've changed:
    for key, value in (
        (CONF_REFRESH_TOKEN, client.refresh_token),
        (CONF_USER_UUID, client.user_uuid),
    ):
        if entry.data.get(key) == value:
            continue
        entry_updates["data"][key] = value

    hass.config_entries.async_update_entry(entry, **entry_updates)

    @callback
    def async_save_refresh_token(refresh_token: str) -> None:
        """Save a refresh token to the config entry data."""
        LOGGER.debug("Saving new refresh token to HASS storage")
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_REFRESH_TOKEN: refresh_token}
        )

    # Create a callback to save the refresh token when it changes:
    entry.async_on_unload(client.add_refresh_token_callback(async_save_refresh_token))

    coordinator = NotionDataUpdateCoordinator(hass, entry=entry, client=client)

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    @callback
    def async_migrate_entity_entry(entry: er.RegistryEntry) -> dict[str, Any] | None:
        """Migrate Notion entity entries.

        This migration focuses on unique IDs, which have changed because of a Notion API
        change:

        Old Format: <sensor_id>_<task_type>
        New Format: <listener_uuid>
        """
        if is_uuid(entry.unique_id):
            # If the unique ID is already a UUID, we don't need to migrate it:
            return None

        sensor_id_str, task_type = entry.unique_id.split("_", 1)
        sensor = next(
            sensor
            for sensor in coordinator.data.sensors.values()
            if sensor.id == int(sensor_id_str)
        )
        listener = next(
            listener
            for listener in coordinator.data.listeners.values()
            if listener.sensor_id == sensor.uuid
            and listener.definition_id == TASK_TYPE_TO_LISTENER_MAP[task_type].value
        )

        return {"new_unique_id": listener.id}

    await er.async_migrate_entries(hass, entry.entry_id, async_migrate_entity_entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Notion config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
