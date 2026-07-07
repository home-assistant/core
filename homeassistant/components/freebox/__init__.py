"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""

from datetime import timedelta
import logging

from freebox_api.exceptions import HttpRequestError

from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
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


async def async_migrate_entry(hass: HomeAssistant, entry: FreeboxConfigEntry) -> bool:
    """Migrate old config entries."""
    if entry.version < 2:
        api = await get_api(hass, entry.data[CONF_HOST])
        try:
            await api.open(entry.data[CONF_HOST], entry.data[CONF_PORT])
            freebox_config = await api.system.get_config()
        except HttpRequestError:
            _LOGGER.warning(
                "Unable to migrate Freebox entry to version 2: cannot reach the router"
            )
            return False
        finally:
            await api.close()

        mac: str = freebox_config["mac"]
        entity_registry = er.async_get(hass)

        migrations: list[tuple[Platform, str, str]] = [
            (platform, f"{mac} {old_suffix}", f"{mac} {new_key}")
            for platform, old_suffix, new_key in _STATIC_UNIQUE_ID_MIGRATIONS
        ]
        migrations.extend(
            (
                Platform.SENSOR,
                f"{mac} Freebox {sensor['name']}",
                f"{mac} {sensor['id']}",
            )
            for sensor in freebox_config.get("sensors", [])
        )

        for platform, old_uid, new_uid in migrations:
            if entity_id := entity_registry.async_get_entity_id(
                platform, DOMAIN, old_uid
            ):
                entity_registry.async_update_entity(entity_id, new_unique_id=new_uid)
                _LOGGER.debug(
                    "Migrated %s unique_id from %s to %s",
                    entity_id,
                    old_uid,
                    new_uid,
                )

        hass.config_entries.async_update_entry(entry, version=2)

    return True


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
