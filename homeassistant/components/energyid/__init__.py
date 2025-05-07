"""The EnergyID integration."""

import datetime as dt
import functools
import logging
from typing import Any, Final, TypeVar, cast

from energyid_webhooks.client_v2 import WebhookClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_ENERGYID_KEY,
    CONF_HA_ENTITY_ID,
    CONF_PROVISIONING_KEY,
    CONF_PROVISIONING_SECRET,
    DATA_CLIENT,
    DATA_LISTENERS,
    DATA_MAPPINGS,
    DEFAULT_UPLOAD_INTERVAL_SECONDS,
    DOMAIN,
    SIGNAL_CONFIG_ENTRY_CHANGED,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Custom type for the EnergyID config entry
EnergyIDClientT = TypeVar("EnergyIDClientT", bound=WebhookClient)
EnergyIDConfigEntry = ConfigEntry[EnergyIDClientT]

# Listener keys
LISTENER_KEY_STATE: Final = "state_listener"
LISTENER_KEY_STOP: Final = "stop_listener"
LISTENER_KEY_CONFIG_UPDATE: Final = "config_update_listener"


async def async_setup_entry(hass: HomeAssistant, entry: EnergyIDConfigEntry) -> bool:
    """Set up EnergyID from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})

    # Initialize listeners as a dictionary
    listeners: dict[str, CALLBACK_TYPE] = {}
    domain_data[DATA_LISTENERS] = listeners
    domain_data[DATA_MAPPINGS] = {}

    session = async_get_clientsession(hass)
    client = WebhookClient(
        provisioning_key=entry.data[CONF_PROVISIONING_KEY],
        provisioning_secret=entry.data[CONF_PROVISIONING_SECRET],
        device_id=entry.data[CONF_DEVICE_ID],
        device_name=entry.data[CONF_DEVICE_NAME],
        session=session,
    )

    # Set the client in runtime_data
    entry.runtime_data = client

    # Also keep in domain_data for backward compatibility
    domain_data[DATA_CLIENT] = client

    @callback
    def _cleanup_all_listeners() -> None:
        """Remove all listeners associated with this entry."""
        _LOGGER.debug("Cleaning up all listeners for %s", entry.entry_id)
        if unsub := listeners.pop(LISTENER_KEY_STATE, None):
            unsub()
        if unsub := listeners.pop(LISTENER_KEY_STOP, None):
            unsub()
        if unsub := listeners.pop(LISTENER_KEY_CONFIG_UPDATE, None):
            unsub()
        domain_data[DATA_LISTENERS] = {}

    async def _close_entry_client(*_: Any) -> None:
        _LOGGER.debug("Closing EnergyID client for %s", entry.runtime_data.device_name)
        await entry.runtime_data.close()

    entry.async_on_unload(_cleanup_all_listeners)
    entry.async_on_unload(_close_entry_client)

    async def _hass_stopping_cleanup(_event: Event) -> None:
        _LOGGER.debug(
            "Home Assistant stopping; ensuring client for %s is closed",
            entry.runtime_data.device_name,
        )
        await entry.runtime_data.close()
        listeners.pop(LISTENER_KEY_STOP, None)

    listeners[LISTENER_KEY_STOP] = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, _hass_stopping_cleanup
    )

    try:
        is_claimed = await entry.runtime_data.authenticate()
        if not is_claimed:
            _LOGGER.warning(
                "EnergyID device '%s' is not claimed. Please claim it. "
                "Data sending will not work until claimed and HA is reloaded/entry reloaded",
                entry.runtime_data.device_name,
            )
        else:
            _LOGGER.info(
                "EnergyID device '%s' authenticated and claimed",
                entry.runtime_data.device_name,
            )
    except Exception as err:
        _LOGGER.error(
            "Failed to authenticate with EnergyID for %s: %s",
            entry.runtime_data.device_name,
            err,
        )
        raise ConfigEntryNotReady(
            f"Failed to authenticate EnergyID for {entry.runtime_data.device_name}: {err}"
        ) from err

    await async_update_listeners(hass, entry)

    listeners[LISTENER_KEY_CONFIG_UPDATE] = entry.add_update_listener(
        async_config_entry_update_listener
    )

    if is_claimed:
        upload_interval = DEFAULT_UPLOAD_INTERVAL_SECONDS
        if entry.runtime_data.webhook_policy:
            upload_interval = (
                entry.runtime_data.webhook_policy.get("uploadInterval")
                or DEFAULT_UPLOAD_INTERVAL_SECONDS
            )
        _LOGGER.info(
            "Starting EnergyID auto-sync for '%s' with interval: %s seconds",
            entry.runtime_data.device_name,
            upload_interval,
        )
        entry.runtime_data.start_auto_sync(interval_seconds=upload_interval)
    else:
        _LOGGER.info(
            "Auto-sync not started for '%s' because device is not claimed",
            entry.runtime_data.device_name,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_config_entry_update_listener(
    hass: HomeAssistant, entry: EnergyIDConfigEntry
) -> None:
    """Handle options update."""
    _LOGGER.debug("Options updated for %s, reloading listeners", entry.entry_id)
    await async_update_listeners(hass, entry)
    async_dispatcher_send(hass, SIGNAL_CONFIG_ENTRY_CHANGED, "options_update", entry)


async def async_update_listeners(
    hass: HomeAssistant, entry: EnergyIDConfigEntry
) -> None:
    """Set up or update state listeners based on current subentries (options)."""
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        _LOGGER.error(
            "Integration data missing for %s during listener update", entry.entry_id
        )
        return

    domain_data = hass.data[DOMAIN][entry.entry_id]
    client = entry.runtime_data
    listeners_dict: dict[str, CALLBACK_TYPE | None] = domain_data[DATA_LISTENERS]

    # Remove existing state listener if it exists
    if old_state_listener := listeners_dict.pop(LISTENER_KEY_STATE, None):
        _LOGGER.debug("Removing old state listener for %s", entry.entry_id)
        old_state_listener()
    # Ensure it's marked as None if no new one is added
    listeners_dict[LISTENER_KEY_STATE] = None

    mappings: dict[str, str] = {}
    entities_to_track: list[str] = []

    for sub_entry_data in entry.options.values():
        if not isinstance(sub_entry_data, dict):
            _LOGGER.warning("Skipping non-dictionary options item: %s", sub_entry_data)
            continue
        ha_entity_id = sub_entry_data.get(CONF_HA_ENTITY_ID)
        energyid_key = sub_entry_data.get(CONF_ENERGYID_KEY)
        if not isinstance(ha_entity_id, str) or not isinstance(energyid_key, str):
            _LOGGER.warning("Skipping invalid mapping data: %s", sub_entry_data)
            continue
        mappings[ha_entity_id] = energyid_key
        entities_to_track.append(ha_entity_id)
        client.get_or_create_sensor(energyid_key)
        _LOGGER.debug(
            "Tracking %s -> %s for %s",
            ha_entity_id,
            energyid_key,
            client.device_name,
        )

    domain_data[DATA_MAPPINGS] = mappings

    if not entities_to_track:
        _LOGGER.info(
            "No entities configured for EnergyID device '%s'",
            client.device_name,
        )
        return

    unsub_state_change = async_track_state_change_event(
        hass,
        entities_to_track,
        functools.partial(_async_handle_state_change, hass, entry.entry_id),
    )
    listeners_dict[LISTENER_KEY_STATE] = unsub_state_change

    _LOGGER.info(
        "Started tracking state changes for %d entities for %s",
        len(entities_to_track),
        client.device_name,
    )


@callback
def _async_handle_state_change(
    hass: HomeAssistant, entry_id: str, event: Event
) -> None:
    """Handle state changes for tracked entities."""
    entity_id = event.data.get("entity_id")
    new_state = event.data.get("new_state")

    if (
        not entity_id
        or new_state is None
        or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
    ):
        return

    try:
        domain_data = hass.data[DOMAIN][entry_id]
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            _LOGGER.error("Failed to get config entry for %s", entry_id)
            return

        # Cast to our typed ConfigEntry
        typed_entry = cast(EnergyIDConfigEntry, entry)
        client = typed_entry.runtime_data

        mappings = domain_data[DATA_MAPPINGS]
        energyid_key = mappings.get(entity_id)
    except KeyError:
        _LOGGER.debug(
            "Integration data not found for entry %s during state change for %s (likely unloading)",
            entry_id,
            entity_id,
        )
        return

    if not energyid_key:
        _LOGGER.debug(
            "No EnergyID key mapping for entity %s in entry %s", entity_id, entry_id
        )
        return

    try:
        value = float(new_state.state)
    except (ValueError, TypeError):
        _LOGGER.warning(
            "Cannot convert state '%s' of %s to float", new_state.state, entity_id
        )
        return

    timestamp = new_state.last_updated
    if not isinstance(timestamp, dt.datetime):
        _LOGGER.warning(
            "Invalid timestamp type (%s) for %s, using current UTC time",
            type(timestamp).__name__,
            entity_id,
        )
        timestamp = dt.datetime.now(dt.UTC)

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=dt.UTC)
    elif timestamp.tzinfo != dt.UTC:
        timestamp = timestamp.astimezone(dt.UTC)

    hass.async_create_task(client.update_sensor(energyid_key, value, timestamp))


async def async_unload_entry(hass: HomeAssistant, entry: EnergyIDConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info(
        "Unloading EnergyID entry for %s",
        entry.data.get(CONF_DEVICE_NAME, entry.entry_id),
    )

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        if DOMAIN in hass.data:
            hass.data[DOMAIN].pop(entry.entry_id, None)
            if not hass.data[DOMAIN]:
                hass.data.pop(DOMAIN, None)
        _LOGGER.debug(
            "Successfully unloaded and cleaned up data for %s", entry.entry_id
        )
    else:
        _LOGGER.error("Failed to unload platforms for %s", entry.entry_id)

    return unload_ok
