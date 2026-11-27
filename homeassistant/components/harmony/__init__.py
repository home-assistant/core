"""The Logitech Harmony Hub integration."""

from functools import partial
import logging
from pathlib import Path

from homeassistant.components.remote import ATTR_ACTIVITY, ATTR_DELAY_SECS
from homeassistant.const import CONF_HOST, CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, HARMONY_OPTIONS_UPDATE, PLATFORMS
from .data import HarmonyConfigEntry, HarmonyData
from .services import async_setup_services
from .util import config_file_path

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Logitech Harmony Hub integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HarmonyConfigEntry) -> None:
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

    entry.async_on_unload(entry.add_update_listener(_update_listener))

    async def _async_on_stop(event: Event) -> None:
        await data.shutdown()

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, _async_on_stop)
    )

    entry.runtime_data = data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


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
                _LOGGER.debug(
                    "Migrating unique_id from [%s] to [%s]",
                    entity_entry.unique_id,
                    activity_id,
                )
                return {"new_unique_id": f"activity_{activity_id}"}

        return None

    await er.async_migrate_entries(hass, entry_id, _async_migrator)


@callback
def _async_import_options_from_data_if_missing(
    hass: HomeAssistant, entry: HarmonyConfigEntry
) -> None:
    options = dict(entry.options)
    modified = 0
    for importable_option in (ATTR_ACTIVITY, ATTR_DELAY_SECS):
        if importable_option not in entry.options and importable_option in entry.data:
            options[importable_option] = entry.data[importable_option]
            modified = 1

    if modified:
        hass.config_entries.async_update_entry(entry, options=options)


async def _update_listener(hass: HomeAssistant, entry: HarmonyConfigEntry) -> None:
    """Reload when the host changes and pass options updates to the entities."""
    if entry.data[CONF_HOST] != entry.runtime_data.address:
        await hass.config_entries.async_reload(entry.entry_id)
        return
    async_dispatcher_send(
        hass, f"{HARMONY_OPTIONS_UPDATE}-{entry.unique_id}", entry.options
    )


def _move_legacy_config_file(hass: HomeAssistant, unique_id: str | None) -> None:
    """Move the hub configuration file from the config root into .storage."""
    old_file = Path(hass.config.path(f"harmony_{unique_id}.conf"))
    if not old_file.exists():
        return
    new_file = Path(config_file_path(hass, unique_id))
    new_file.parent.mkdir(parents=True, exist_ok=True)
    old_file.replace(new_file)


async def async_migrate_entry(hass: HomeAssistant, entry: HarmonyConfigEntry) -> None:
    """Migrate old entry."""
    if entry.version == 1 and entry.minor_version < 2:
        await hass.async_add_executor_job(
            _move_legacy_config_file, hass, entry.unique_id
        )
        hass.config_entries.async_update_entry(entry, minor_version=2)


async def async_unload_entry(hass: HomeAssistant, entry: HarmonyConfigEntry) -> None:
    """Unload a config entry."""
    try:
        await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    finally:
        # Shutdown a harmony remote for removal
        await entry.runtime_data.shutdown()


async def async_remove_entry(hass: HomeAssistant, entry: HarmonyConfigEntry) -> None:
    """Remove the hub configuration file."""
    await hass.async_add_executor_job(
        partial(Path(config_file_path(hass, entry.unique_id)).unlink, missing_ok=True)
    )
