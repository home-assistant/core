"""The EnergyID integration."""

import datetime as dt
import functools
import logging
from typing import Any

from energyid_webhooks.client_v2 import WebhookClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EnergyID from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_MAPPINGS: {},
        DATA_LISTENERS: [],
    }

    session = async_get_clientsession(hass)
    client = WebhookClient(
        provisioning_key=entry.data[CONF_PROVISIONING_KEY],
        provisioning_secret=entry.data[CONF_PROVISIONING_SECRET],
        device_id=entry.data[CONF_DEVICE_ID],
        device_name=entry.data[CONF_DEVICE_NAME],
        session=session,
    )
    hass.data[DOMAIN][entry.entry_id][DATA_CLIENT] = client

    is_claimed = False
    try:
        is_claimed = await client.authenticate()
        if not is_claimed:
            _LOGGER.warning(
                "EnergyID device '%s' is not claimed. Please claim it via the EnergyID website. "
                "Data sending will not work until claimed and HA is restarted or the entry is reloaded",
                entry.data[CONF_DEVICE_NAME],
            )
        else:
            _LOGGER.info(
                "EnergyID device '%s' authenticated and claimed",
                entry.data[CONF_DEVICE_NAME],
            )

    except Exception as err:
        _LOGGER.error("Failed to authenticate with EnergyID during setup: %s", err)
        raise ConfigEntryNotReady(f"Failed to authenticate EnergyID: {err}") from err

    await async_update_listeners(hass, entry)

    update_listener_remover = entry.add_update_listener(
        async_config_entry_update_listener
    )

    if is_claimed:
        upload_interval = getattr(
            client, "uploadInterval", DEFAULT_UPLOAD_INTERVAL_SECONDS
        )
        _LOGGER.info(
            "Starting EnergyID auto-sync with interval: %s seconds", upload_interval
        )
        client.start_auto_sync(interval_seconds=upload_interval)
    else:
        _LOGGER.info(
            "Auto-sync not started because device '%s' is not claimed",
            entry.data[CONF_DEVICE_NAME],
        )

    @callback
    def _async_cleanup_listeners() -> None:
        """Remove state listeners."""
        _LOGGER.debug("Cleaning up listeners for %s", entry.entry_id)
        if (
            listeners := hass.data[DOMAIN]
            .get(entry.entry_id, {})
            .pop(DATA_LISTENERS, None)
        ):
            for unsub in listeners:
                unsub()

    async def _async_close_client(*_: Any) -> None:
        """Close client session."""
        _LOGGER.debug("Closing EnergyID client for %s", entry.entry_id)
        if client := hass.data[DOMAIN].get(entry.entry_id, {}).get(DATA_CLIENT):
            await client.close()

    entry.async_on_unload(_async_cleanup_listeners)
    entry.async_on_unload(update_listener_remover)
    entry.async_on_unload(_async_close_client)
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close_client)
    )

    # Forward setup to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_config_entry_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update."""
    _LOGGER.debug("Options updated for %s, reloading listeners", entry.entry_id)
    await async_update_listeners(hass, entry)


async def async_update_listeners(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up or update state listeners based on current subentries (options)."""
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        _LOGGER.error(
            "Integration data missing for %s during listener update", entry.entry_id
        )
        return

    domain_data = hass.data[DOMAIN][entry.entry_id]
    client: WebhookClient = domain_data[DATA_CLIENT]
    new_listeners: list[CALLBACK_TYPE] = []

    if old_listeners := domain_data.get(DATA_LISTENERS):
        _LOGGER.debug(
            "Removing %d old listeners for %s", len(old_listeners), entry.entry_id
        )
        for unsub in old_listeners:
            unsub()
        old_listeners.clear()
    domain_data[DATA_LISTENERS] = new_listeners

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
        _LOGGER.debug("Tracking %s -> %s", ha_entity_id, energyid_key)

    domain_data[DATA_MAPPINGS] = mappings

    if not entities_to_track:
        _LOGGER.info(
            "No entities configured for EnergyID device '%s'",
            entry.data[CONF_DEVICE_NAME],
        )
        return

    unsub = async_track_state_change_event(
        hass,
        entities_to_track,
        functools.partial(_async_handle_state_change, hass, entry.entry_id),
    )
    new_listeners.append(unsub)

    _LOGGER.info(
        "Started tracking state changes for %d entities", len(entities_to_track)
    )


@callback
def _async_handle_state_change(
    hass: HomeAssistant,
    entry_id: str,
    event: Event,
) -> None:
    """Handle state changes for tracked entities."""
    entity_id = event.data.get("entity_id")
    new_state = event.data.get("new_state")

    if (
        not entity_id
        or new_state is None
        or new_state.state in ("unknown", "unavailable")
    ):
        return

    try:
        domain_data = hass.data[DOMAIN][entry_id]
        client: WebhookClient = domain_data[DATA_CLIENT]
        mappings = domain_data.get(DATA_MAPPINGS, {})
        energyid_key = mappings.get(entity_id)
    except KeyError:
        _LOGGER.debug(
            "Integration data not found for entry %s during state change for %s (likely unloading)",
            entry_id,
            entity_id,
        )
        return

    if not client or not energyid_key:
        _LOGGER.debug(
            "No active EnergyID client/mapping for entity %s in entry %s",
            entity_id,
            entry_id,
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
            "Invalid timestamp type (%s) for %s, using current time",
            type(timestamp).__name__,
            entity_id,
        )
        timestamp = dt.datetime.now(dt.UTC)

    hass.async_create_task(client.update_sensor(energyid_key, value, timestamp))


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading EnergyID entry for %s", entry.data[CONF_DEVICE_NAME])

    # Unload platforms first
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Clean up the domain data
        if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
            hass.data[DOMAIN].pop(entry.entry_id, None)

        # Clean up domain if last entry
        if DOMAIN in hass.data and not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN, None)

    _LOGGER.debug(
        "Finished unloading process for %s. Success: %s", entry.entry_id, unload_ok
    )
    return unload_ok
