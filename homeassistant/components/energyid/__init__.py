"""The EnergyID integration."""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
from datetime import timedelta
import functools
import logging

from energyid_webhooks.client_v2 import WebhookClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import (
    async_track_entity_registry_updated_event,
    async_track_state_change_event,
    async_track_time_interval,
)

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

DEFAULT_UPLOAD_INTERVAL_SECONDS = 60


@dataclass
class EnergyIDRuntimeData:
    """Runtime data for the EnergyID integration."""

    client: WebhookClient
    mappings: dict[str, str]
    state_listener: CALLBACK_TYPE | None = None
    registry_tracking_listener: CALLBACK_TYPE | None = None
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
        mappings={},
    )

    is_claimed = None
    try:
        is_claimed = await client.authenticate()
    except TimeoutError as err:
        raise ConfigEntryNotReady(
            f"Timeout authenticating with EnergyID: {err}"
        ) from err
    # Catch all other exceptions as fatal authentication failures
    except Exception as err:
        _LOGGER.exception("Unexpected error during EnergyID authentication")
        raise ConfigEntryAuthFailed(
            f"Failed to authenticate with EnergyID: {err}"
        ) from err
    if not is_claimed:
        raise ConfigEntryAuthFailed("Device is not claimed. Please re-authenticate.")

    _LOGGER.debug("EnergyID device '%s' authenticated successfully", client.device_name)

    async def _async_synchronize_sensors(now: dt.datetime | None = None) -> None:
        """Callback for periodically synchronizing sensor data."""
        try:
            await client.synchronize_sensors()
            if entry.runtime_data.unavailable_logged:
                _LOGGER.debug("Connection to EnergyID re-established")
                entry.runtime_data.unavailable_logged = False
        except (OSError, RuntimeError) as err:
            if not entry.runtime_data.unavailable_logged:
                _LOGGER.debug("EnergyID is unavailable: %s", err)
                entry.runtime_data.unavailable_logged = True

    upload_interval = DEFAULT_UPLOAD_INTERVAL_SECONDS
    if client.webhook_policy:
        upload_interval = client.webhook_policy.get(
            "uploadInterval", DEFAULT_UPLOAD_INTERVAL_SECONDS
        )

    # Schedule the callback and automatically unsubscribe when the entry is unloaded.
    entry.async_on_unload(
        async_track_time_interval(
            hass, _async_synchronize_sensors, timedelta(seconds=upload_interval)
        )
    )
    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))

    update_listeners(hass, entry)

    _LOGGER.debug(
        "Starting EnergyID background sync for '%s'",
        client.device_name,
    )

    return True


async def config_entry_update_listener(
    hass: HomeAssistant, entry: EnergyIDConfigEntry
) -> None:
    """Handle config entry updates, including subentry changes."""
    _LOGGER.debug("Config entry updated for %s, reloading listeners", entry.entry_id)
    update_listeners(hass, entry)


@callback
def update_listeners(hass: HomeAssistant, entry: EnergyIDConfigEntry) -> None:
    """Set up or update state listeners and queue initial states."""
    runtime_data = entry.runtime_data
    client = runtime_data.client

    # Clean up old state listener
    if runtime_data.state_listener:
        runtime_data.state_listener()
        runtime_data.state_listener = None

    mappings: dict[str, str] = {}
    entities_to_track: list[str] = []
    old_mappings = set(runtime_data.mappings.keys())
    new_mappings = set()
    ent_reg = er.async_get(hass)

    subentries = list(entry.subentries.values())
    _LOGGER.debug(
        "Found %d subentries in entry.subentries: %s",
        len(subentries),
        [s.data for s in subentries],
    )

    # Build current entity mappings
    tracked_entity_ids = []
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
        tracked_entity_ids.append(ha_entity_id)

        if not hass.states.get(ha_entity_id):
            # Entity exists in registry but not yet in state machine (common during boot)
            _LOGGER.debug(
                "Entity %s does not exist in state machine yet, will track when available (mapping to %s)",
                ha_entity_id,
                energyid_key,
            )
            # Still add to entities_to_track so we can handle it when state appears
            entities_to_track.append(ha_entity_id)
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

    # Clean up old entity registry listener
    if runtime_data.registry_tracking_listener:
        runtime_data.registry_tracking_listener()
        runtime_data.registry_tracking_listener = None

    # Set up listeners for entity registry changes
    if tracked_entity_ids:
        _LOGGER.debug("Setting up entity registry tracking for: %s", tracked_entity_ids)

        def _handle_entity_registry_change(
            event: Event[er.EventEntityRegistryUpdatedData],
        ) -> None:
            """Handle entity registry changes for our tracked entities."""
            _LOGGER.debug("Registry event for tracked entity: %s", event.data)

            if event.data["action"] == "update":
                # Type is now narrowed to _EventEntityRegistryUpdatedData_Update
                if "entity_id" in event.data["changes"]:
                    old_entity_id = event.data["changes"]["entity_id"]
                    new_entity_id = event.data["entity_id"]

                    _LOGGER.debug(
                        "Tracked entity ID changed: %s -> %s",
                        old_entity_id,
                        new_entity_id,
                    )
                    # Entity ID changed, need to reload listeners to track new ID
                    update_listeners(hass, entry)

            elif event.data["action"] == "remove":
                _LOGGER.debug("Tracked entity removed: %s", event.data["entity_id"])
                # reminder: Create repair issue to notify user about removed entity
                update_listeners(hass, entry)

        # Track the specific entity IDs we care about
        unsub_entity_registry = async_track_entity_registry_updated_event(
            hass, tracked_entity_ids, _handle_entity_registry_change
        )
        runtime_data.registry_tracking_listener = unsub_entity_registry

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
    runtime_data.state_listener = unsub_state_change

    _LOGGER.debug(
        "Now tracking state changes for %d entities for '%s': %s",
        len(entities_to_track),
        client.device_name,
        entities_to_track,
    )


@callback
def _async_handle_state_change(
    hass: HomeAssistant, entry_id: str, event: Event[EventStateChangedData]
) -> None:
    """Handle state changes for tracked entities."""
    entity_id = event.data["entity_id"]
    new_state = event.data["new_state"]

    _LOGGER.debug(
        "State change detected for entity: %s, new value: %s",
        entity_id,
        new_state.state if new_state else "None",
    )

    if not new_state or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return

    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry or not hasattr(entry, "runtime_data"):
        # Entry is being unloaded or not yet fully initialized
        return

    runtime_data = entry.runtime_data
    client = runtime_data.client

    # Check if entity is already mapped
    if energyid_key := runtime_data.mappings.get(entity_id):
        # Entity already mapped, just update value
        _LOGGER.debug(
            "Updating EnergyID sensor %s with value %s", energyid_key, new_state.state
        )
    else:
        # Entity not mapped yet - check if it should be (handles late-appearing entities)
        ent_reg = er.async_get(hass)
        for subentry in entry.subentries.values():
            entity_uuid = subentry.data.get(CONF_HA_ENTITY_UUID)
            energyid_key_candidate = subentry.data.get(CONF_ENERGYID_KEY)

            if not (entity_uuid and energyid_key_candidate):
                continue

            entity_entry = ent_reg.async_get(entity_uuid)
            if entity_entry and entity_entry.entity_id == entity_id:
                # Found it! Add to mappings and send initial value
                energyid_key = energyid_key_candidate
                runtime_data.mappings[entity_id] = energyid_key
                client.get_or_create_sensor(energyid_key)
                _LOGGER.debug(
                    "Entity %s now available in state machine, adding to mappings (key: %s)",
                    entity_id,
                    energyid_key,
                )
                break
        else:
            # Not a tracked entity, ignore
            return

    try:
        value = float(new_state.state)
    except (ValueError, TypeError):
        return

    client.get_or_create_sensor(energyid_key).update(value, new_state.last_updated)


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
            runtime_data = entry.runtime_data

            # Remove state listener
            if runtime_data.state_listener:
                runtime_data.state_listener()

            # Remove registry tracking listener
            if runtime_data.registry_tracking_listener:
                runtime_data.registry_tracking_listener()

            try:
                await runtime_data.client.close()
            except Exception:
                _LOGGER.exception("Error closing EnergyID client for %s", entry.title)
            del entry.runtime_data
    except Exception:
        _LOGGER.exception("Error during async_unload_entry for %s", entry.title)
        return False
    return True
