"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""

from datetime import timedelta
import logging

from freebox_api.exceptions import HttpRequestError

from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, PLATFORMS
from .router import FreeboxConfigEntry, FreeboxRouter, get_api

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

# Old entity name suffixes that need rewriting to the entity description key.
# Format: (platform, old name suffix, new key)
_STATIC_UNIQUE_ID_MIGRATIONS: tuple[tuple[Platform, str, str], ...] = (
    (Platform.SENSOR, "Freebox download speed", "rate_down"),
    (Platform.SENSOR, "Freebox upload speed", "rate_up"),
    (Platform.SENSOR, "Freebox missed calls", "missed"),
    (Platform.BUTTON, "Reboot Freebox", "reboot"),
    (Platform.BUTTON, "Mark calls as read", "mark_calls_as_read"),
    (Platform.SWITCH, "Freebox WiFi", "wifi"),
)


@callback
def _migrate_unique_ids(hass: HomeAssistant, router: FreeboxRouter) -> None:
    """Migrate name-based unique ids to key-based ones."""
    entity_registry = er.async_get(hass)
    mac = router.mac

    for platform, old_suffix, new_key in _STATIC_UNIQUE_ID_MIGRATIONS:
        old_uid = f"{mac} {old_suffix}"
        new_uid = f"{mac} {new_key}"
        if entity_id := entity_registry.async_get_entity_id(platform, DOMAIN, old_uid):
            try:
                entity_registry.async_update_entity(entity_id, new_unique_id=new_uid)
            except ValueError:
                _LOGGER.warning(
                    "Unable to migrate unique_id from %s to %s: target already exists",
                    old_uid,
                    new_uid,
                )
                continue
            _LOGGER.debug(
                "Migrated %s unique_id from %s to %s", entity_id, old_uid, new_uid
            )

    for sensor_id, sensor_name in router.sensors_temperature_names.items():
        old_uid = f"{mac} Freebox {sensor_name}"
        new_uid = f"{mac} {sensor_id}"
        if entity_id := entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, old_uid
        ):
            try:
                entity_registry.async_update_entity(entity_id, new_unique_id=new_uid)
            except ValueError:
                _LOGGER.warning(
                    "Unable to migrate unique_id from %s to %s: target already exists",
                    old_uid,
                    new_uid,
                )
                continue
            _LOGGER.debug(
                "Migrated %s unique_id from %s to %s", entity_id, old_uid, new_uid
            )


async def async_setup_entry(hass: HomeAssistant, entry: FreeboxConfigEntry) -> bool:
    """Set up Freebox entry."""
    api = await get_api(hass, entry.data[CONF_HOST])
    try:
        await api.open(entry.data[CONF_HOST], entry.data[CONF_PORT])
    except HttpRequestError as err:
        raise ConfigEntryNotReady from err

    freebox_config = await api.system.get_config()

    router = FreeboxRouter(hass, entry, api, freebox_config)
    await router.update_all()
    entry.async_on_unload(
        async_track_time_interval(hass, router.update_all, SCAN_INTERVAL)
    )

    _migrate_unique_ids(hass, router)

    entry.runtime_data = router

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_close_connection(event: Event) -> None:
        """Close Freebox connection on HA Stop."""
        await router.close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )
    entry.async_on_unload(router.close)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FreeboxConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
