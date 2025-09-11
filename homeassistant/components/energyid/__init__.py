"""The EnergyID integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import datetime as dt
import functools
import logging
from typing import Final

from energyid_webhooks.client_v2 import WebhookClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_ENERGYID_KEY,
    CONF_HA_ENTITY_UUID,
    CONF_PROVISIONING_KEY,
    CONF_PROVISIONING_SECRET,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

type EnergyIDConfigEntry = ConfigEntry[EnergyIDRuntimeData]
LISTENER_KEY_STATE: Final = "state_listener"
LISTENER_KEY_STOP: Final = "stop_listener"
LISTENER_KEY_CONFIG_UPDATE: Final = "config_update_listener"

DEFAULT_UPLOAD_INTERVAL_SECONDS: Final = 60


@dataclass
class EnergyIDRuntimeData:
    """Runtime data for the EnergyID integration."""

    client: WebhookClient
    listeners: dict[str, CALLBACK_TYPE | asyncio.Task[None]]
    mappings: dict[str, str]
    unavailable_logged: bool = False


async def async_setup_entry(hass: HomeAssistant, entry: EnergyIDConfigEntry) -> bool:
    """Set up EnergyID from a config entry."""
    session = async_get_clientsession(hass)
    client = WebhookClient(
        provisioning_key=entry.data[CONF_PROVISIONING_KEY],
        provisioning_secret=entry.data[CONF_PROVISIONING_SECRET],
        device_id=entry.data[CONF_DEVICE_ID],
        device_name=entry.data[CONF_DEVICE_NAME],
        session=session,
    )

    entry.runtime_data = EnergyIDRuntimeData(
        client=client,
        listeners={},
        mappings={},
    )

    is_claimed = None
    try:
        is_claimed = await client.authenticate()
    except TimeoutError as err:
        raise ConfigEntryNotReady(
            f"Timeout authenticating with EnergyID: {err}"
        ) from err
    except Exception as err:
        raise ConfigEntryAuthFailed(
            f"Failed to authenticate with EnergyID: {err}"
        ) from err
    if not is_claimed:
        raise ConfigEntryAuthFailed("Device is not claimed. Please re-authenticate.")

    _LOGGER.debug("EnergyID device '%s' authenticated successfully", client.device_name)

    async def _async_background_sync() -> None:
        """Background task to synchronize sensor data and log unavailability only once."""
        while True:
            try:
                await client.synchronize_sensors()
                if entry.runtime_data.unavailable_logged:
                    _LOGGER.info("Connection to EnergyID re-established")
                    entry.runtime_data.unavailable_logged = False
            except (OSError, RuntimeError) as err:
                if not entry.runtime_data.unavailable_logged:
                    _LOGGER.info("EnergyID is unavailable: %s", err)
                    entry.runtime_data.unavailable_logged = True
            upload_interval = DEFAULT_UPLOAD_INTERVAL_SECONDS
            if client.webhook_policy:
                upload_interval = client.webhook_policy.get(
                    "uploadInterval", DEFAULT_UPLOAD_INTERVAL_SECONDS
                )
            await asyncio.sleep(upload_interval)

    sync_task = hass.async_create_task(_async_background_sync())
    entry.runtime_data.listeners["background_sync"] = sync_task
    entry.async_on_unload(entry.add_update_listener(async_config_entry_update_listener))

    await async_update_listeners(hass, entry)

    _LOGGER.debug(
        "Starting EnergyID background sync for '%s'",
        client.device_name,
    )

    return True


async def async_config_entry_update_listener(
    hass: HomeAssistant, entry: EnergyIDConfigEntry
) -> None:
    """Handle config entry updates, including subentry changes."""
    _LOGGER.debug("Config entry updated for %s, reloading listeners", entry.entry_id)
    await async_update_listeners(hass, entry)


async def async_update_listeners(
    hass: HomeAssistant, entry: EnergyIDConfigEntry
) -> None:
    """Set up or update state listeners and queue initial states."""
    runtime_data = entry.runtime_data
    client = runtime_data.client

    if old_state_listener := runtime_data.listeners.pop(LISTENER_KEY_STATE, None):
        _LOGGER.debug("Removing old state listener for %s", entry.entry_id)
        if isinstance(old_state_listener, asyncio.Task):
            old_state_listener.cancel()
        else:
            old_state_listener()

    mappings: dict[str, str] = {}
    entities_to_track: list[str] = []
    old_mappings = set(runtime_data.mappings.keys())
    new_mappings = set()
    ent_reg = er.async_get(hass)

    subentries = list(entry.subentries.values()) if hasattr(entry, "subentries") else []
    _LOGGER.debug(
        "Found %d subentries in entry.subentries: %s",
        len(subentries),
        [s.data for s in subentries],
    )

    for subentry in subentries:
        entity_uuid = subentry.data.get(CONF_HA_ENTITY_UUID)
        energyid_key = subentry.data.get(CONF_ENERGYID_KEY)

        if not (entity_uuid and energyid_key):
            continue

        entity_entry = ent_reg.async_get(entity_uuid)
        if not entity_entry:
            _LOGGER.warning(
                "Entity with UUID %s does not exist, skipping mapping to %s",
                entity_uuid,
                energyid_key,
            )
            continue

        ha_entity_id = entity_entry.entity_id

        if not hass.states.get(ha_entity_id):
            _LOGGER.warning(
                "Entity %s does not exist in state machine, skipping mapping to %s",
                ha_entity_id,
                energyid_key,
            )
            continue

        mappings[ha_entity_id] = energyid_key
        entities_to_track.append(ha_entity_id)
        new_mappings.add(ha_entity_id)
        client.get_or_create_sensor(energyid_key)

        if ha_entity_id not in old_mappings:
            _LOGGER.debug(
                "New mapping detected for %s, queuing initial state", ha_entity_id
            )
            if (
                current_state := hass.states.get(ha_entity_id)
            ) and current_state.state not in (
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ):
                try:
                    value = float(current_state.state)
                    timestamp = current_state.last_updated or dt.datetime.now(dt.UTC)
                    client.get_or_create_sensor(energyid_key).update(value, timestamp)
                except (ValueError, TypeError):
                    _LOGGER.debug(
                        "Could not convert initial state of %s to float: %s",
                        ha_entity_id,
                        current_state.state,
                    )

    if removed_mappings := old_mappings - new_mappings:
        _LOGGER.debug("Removed mappings: %s", ", ".join(removed_mappings))

    runtime_data.mappings = mappings

    if not entities_to_track:
        _LOGGER.debug(
            "No valid sensor mappings configured for '%s'", client.device_name
        )
        return

    unsub_state_change = async_track_state_change_event(
        hass,
        entities_to_track,
        functools.partial(_async_handle_state_change, hass, entry.entry_id),
    )
    runtime_data.listeners[LISTENER_KEY_STATE] = unsub_state_change

    _LOGGER.debug(
        "Now tracking state changes for %d entities for '%s' (interval: %ss)",
        len(entities_to_track),
        client.device_name,
        client.webhook_policy.get("uploadInterval", DEFAULT_UPLOAD_INTERVAL_SECONDS)
        if client.webhook_policy
        else DEFAULT_UPLOAD_INTERVAL_SECONDS,
    )


@callback
def _async_handle_state_change(
    hass: HomeAssistant, entry_id: str, event: Event
) -> None:
    """Handle state changes for tracked entities."""
    entity_id = event.data["entity_id"]
    new_state = event.data.get("new_state")

    if not new_state or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return

    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry or not hasattr(entry, "runtime_data"):
        return

    runtime_data = entry.runtime_data
    if not (energyid_key := runtime_data.mappings.get(entity_id)):
        return

    try:
        value = float(new_state.state)
    except (ValueError, TypeError):
        return

    runtime_data.client.get_or_create_sensor(energyid_key).update(
        value, new_state.last_updated
    )


async def async_unload_entry(hass: HomeAssistant, entry: EnergyIDConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading EnergyID entry for %s", entry.title)

    try:
        # Unload subentries if present (guarded for test and reload scenarios)
        if hasattr(hass.config_entries, "async_entries") and hasattr(entry, "entry_id"):
            subentries = [
                e.entry_id
                for e in hass.config_entries.async_entries(DOMAIN)
                if getattr(e, "parent_entry", None) == entry.entry_id
            ]
            for subentry_id in subentries:
                await hass.config_entries.async_unload(subentry_id)

        # Only clean up listeners and client if runtime_data is present
        if hasattr(entry, "runtime_data"):
            for listener in entry.runtime_data.listeners.values():
                if hasattr(listener, "cancel"):
                    listener.cancel()  # It's a task
                else:
                    listener()  # It's a callable

            try:
                await entry.runtime_data.client.close()
            except Exception:
                _LOGGER.exception("Error closing EnergyID client for %s", entry.title)
            del entry.runtime_data
    except Exception:
        _LOGGER.exception("Error during async_unload_entry for %s", entry.title)
        return False
    return True
