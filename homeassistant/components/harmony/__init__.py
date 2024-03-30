"""The Logitech Harmony Hub integration."""

import logging

from homeassistant.components.remote import ATTR_ACTIVITY, ATTR_DELAY_SECS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CANCEL_LISTENER,
    CANCEL_STOP,
    DOMAIN,
    HARMONY_DATA,
    HARMONY_OPTIONS_UPDATE,
    PLATFORMS,
)
from .data import HarmonyData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Logitech Harmony Hub from a config entry."""
    # As there currently is no way to import options from yaml
    # when setting up a config entry, we fallback to adding
    # the options to the config entry and pull them out here if
    # they are missing from the options
    _async_import_options_from_data_if_missing(hass, entry)

    address = entry.data[CONF_HOST]
    name = entry.data[CONF_NAME]
    data = HarmonyData(hass, address, name, entry.unique_id)
    await data.connect()

    await _migrate_old_unique_ids(hass, entry.entry_id, data)

    cancel_listener = entry.add_update_listener(_update_listener)

    async def _async_on_stop(event: Event) -> None:
        await data.shutdown()

    cancel_stop = hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, _async_on_stop)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        HARMONY_DATA: data,
        CANCEL_LISTENER: cancel_listener,
        CANCEL_STOP: cancel_stop,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _migrate_old_unique_ids(
    hass: HomeAssistant, entry_id: str, data: HarmonyData
) -> None:
    names_to_ids = {activity["label"]: activity["id"] for activity in data.activities}

    @callback
    def _async_migrator(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
        # Old format for switches was {remote_unique_id}-{activity_name}
        # New format is activity_{activity_id}
        parts = entity_entry.unique_id.split("-", 1)
        if len(parts) > 1:  # old format
            activity_name = parts[1]
            activity_id = names_to_ids.get(activity_name)

            if activity_id is not None:
                _LOGGER.info(
                    "Migrating unique_id from [%s] to [%s]",
                    entity_entry.unique_id,
                    activity_id,
                )
                return {"new_unique_id": f"activity_{activity_id}"}

        return None

    await er.async_migrate_entries(hass, entry_id, _async_migrator)


@callback
def _async_import_options_from_data_if_missing(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    options = dict(entry.options)
    modified = 0
    for importable_option in (ATTR_ACTIVITY, ATTR_DELAY_SECS):
        if importable_option not in entry.options and importable_option in entry.data:
            options[importable_option] = entry.data[importable_option]
            modified = 1

    if modified:
        hass.config_entries.async_update_entry(entry, options=options)


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    async_dispatcher_send(
        hass, f"{HARMONY_OPTIONS_UPDATE}-{entry.unique_id}", entry.options
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Shutdown a harmony remote for removal
    entry_data = hass.data[DOMAIN][entry.entry_id]
    entry_data[CANCEL_LISTENER]()
    entry_data[CANCEL_STOP]()
    await entry_data[HARMONY_DATA].shutdown()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
