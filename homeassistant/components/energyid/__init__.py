"""The EnergyID integration."""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import functools
import logging
from typing import Final

from energyid_webhooks.client_v2 import WebhookClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_ENERGYID_KEY,
    CONF_HA_ENTITY_ID,
    CONF_PROVISIONING_KEY,
    CONF_PROVISIONING_SECRET,
)

_LOGGER = logging.getLogger(__name__)

type EnergyIDConfigEntry = ConfigEntry[EnergyIDRuntimeData]
LISTENER_KEY_STATE: Final = "state_listener"
LISTENER_KEY_STOP: Final = "stop_listener"
LISTENER_KEY_CONFIG_UPDATE: Final = "config_update_listener"

DEFAULT_UPLOAD_INTERVAL_SECONDS: Final = 60


@dataclass
class EnergyIDRuntimeData:
    """Runtime data for the EnergyID integration.

    Attributes:
        client: The WebhookClient instance for EnergyID API communication.
        listeners: Dictionary of event listeners for this config entry.
        mappings: Dictionary mapping Home Assistant entity IDs to EnergyID keys.
    """

    client: WebhookClient
    listeners: dict[str, CALLBACK_TYPE]
    mappings: dict[str, str]


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

    async def _authenticate_client() -> None:
        """Authenticate the client and handle errors appropriately."""
        try:
            is_claimed = await client.authenticate()
        except TimeoutError as err:
            raise ConfigEntryNotReady(
                f"Timeout authenticating with EnergyID: {err}"
            ) from err
        except Exception as err:
            _LOGGER.exception("Unexpected error authenticating with EnergyID")
            raise ConfigEntryNotReady(
                f"Unexpected error authenticating with EnergyID: {err}"
            ) from err

        if not is_claimed:
            raise ConfigEntryError(
                "Device is not claimed. Please claim the device first."
            )

    await _authenticate_client()

    _LOGGER.debug("EnergyID device '%s' authenticated successfully", client.device_name)

    # Register update listener
    entry.async_on_unload(entry.add_update_listener(async_config_entry_update_listener))

    # Set up listeners for sensor mappings
    await async_update_listeners(hass, entry)

    # Start the background auto-sync task
    upload_interval = DEFAULT_UPLOAD_INTERVAL_SECONDS
    if client.webhook_policy:
        upload_interval = client.webhook_policy.get(
            "uploadInterval", DEFAULT_UPLOAD_INTERVAL_SECONDS
        )
    _LOGGER.debug(
        "Starting EnergyID auto-sync for '%s' with interval: %s seconds",
        client.device_name,
        upload_interval,
    )
    client.start_auto_sync(interval_seconds=upload_interval)

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

    # Remove old state listener if it exists
    if old_state_listener := runtime_data.listeners.pop(LISTENER_KEY_STATE, None):
        _LOGGER.debug("Removing old state listener for %s", entry.entry_id)
        old_state_listener()

    mappings: dict[str, str] = {}
    entities_to_track: list[str] = []

    # Track removed mappings for debug logging
    old_mappings = set(runtime_data.mappings.keys())
    new_mappings = set()

    for subentry in entry.subentries.values():
        subentry_data = subentry.data
        ha_entity_id = subentry_data.get(CONF_HA_ENTITY_ID)
        energyid_key = subentry_data.get(CONF_ENERGYID_KEY)

        if not (ha_entity_id and energyid_key):
            continue

        if not hass.states.get(ha_entity_id):
            _LOGGER.warning(
                "Entity %s does not exist, skipping mapping to %s",
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
                    _LOGGER.debug(
                        "Queued initial state for %s -> %s: %s",
                        ha_entity_id,
                        energyid_key,
                        value,
                    )
                except (ValueError, TypeError):
                    _LOGGER.debug(
                        "Could not convert initial state of %s to float: %s",
                        ha_entity_id,
                        current_state.state,
                    )

    # Log removed mappings
    removed_mappings = old_mappings - new_mappings
    if removed_mappings:
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
        "Now tracking state changes for %d entities for '%s': %s",
        len(entities_to_track),
        client.device_name,
        ", ".join(entities_to_track),
    )


@callback
def _async_handle_state_change(
    hass: HomeAssistant, entry_id: str, event: Event
) -> None:
    """Handle state changes for tracked entities and queue them for the next sync."""
    # State change events always have entity_id in their data
    entity_id = event.data["entity_id"]
    new_state = event.data.get("new_state")

    # If new_state is None, the entity has been removed from the state machine
    # We don't need to handle this specially as we only care about state changes
    if not new_state or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return

    # Guard against race condition where state change events might be processed
    # after the config entry has been unloaded or during unloading
    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry or not hasattr(entry, "runtime_data"):
        _LOGGER.debug(
            "State change for %s ignored: entry %s not ready or unloading",
            entity_id,
            entry_id,
        )
        return

    runtime_data = entry.runtime_data
    # Ensure this state change is for a currently mapped entity
    # This guard is needed in case entity mappings changed but we're still processing
    # events from the previous tracking period
    if not (energyid_key := runtime_data.mappings.get(entity_id)):
        return

    try:
        value = float(new_state.state)
    except (ValueError, TypeError):
        # Sensor base entities should guard against this, but we log at debug level
        # for troubleshooting outdated custom integrations
        _LOGGER.debug(
            "Cannot convert state '%s' of %s to float", new_state.state, entity_id
        )
        return

    # Use the client's internal caching; the background sync will handle the upload
    runtime_data.client.get_or_create_sensor(energyid_key).update(
        value, new_state.last_updated
    )

    _LOGGER.debug(
        "Queued state change for %s -> %s: %s", entity_id, energyid_key, value
    )


async def async_unload_entry(hass: HomeAssistant, entry: EnergyIDConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading EnergyID entry for %s", entry.title)
    try:
        runtime_data = getattr(entry, "runtime_data", None)
        if runtime_data:
            # Stop listeners
            for unsub in runtime_data.listeners.values():
                unsub()
            # Close client
            try:
                await runtime_data.client.close()
            except Exception:
                _LOGGER.exception("Error closing EnergyID client for %s", entry.title)
            # Clean up
            del entry.runtime_data
    except Exception:
        _LOGGER.exception("Error during async_unload_entry for %s", entry.title)
        return False
    return True
