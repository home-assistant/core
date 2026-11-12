"""Alexa Devices integration."""

from collections.abc import Awaitable, Callable
from contextlib import suppress
from pathlib import Path

from aioamazondevices.api import SETTINGS_FILENAME

from homeassistant.const import CONF_COUNTRY, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv, httpx_client
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.ssl import SSL_ALPN_HTTP11_HTTP2

from .const import CONF_LOGIN_DATA, CONF_SITE, COUNTRY_DOMAINS, DOMAIN, LOGGER
from .coordinator import AmazonConfigEntry, AmazonDevicesCoordinator
from .services import async_setup_services

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.LIGHT,
    Platform.MEDIA_PLAYER,
    Platform.NOTIFY,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TODO,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Alexa Devices component."""
    async_setup_services(hass)
    return True


async def _async_initial_sync(sync_call: Callable[[], Awaitable[None]]) -> None:
    """Run an initial best-effort sync call.

    These syncs are not required for setup to succeed: a failing Amazon API
    call must not prevent the other syncs from running or abort setup.
    """
    try:
        await sync_call()
    except ConfigEntryNotReady as err:
        LOGGER.warning(
            "Initial sync failed for %s: %s. Data may be missing or incomplete until updates are pushed by Amazon",
            sync_call.__name__,
            err,
        )


async def async_setup_entry(hass: HomeAssistant, entry: AmazonConfigEntry) -> None:
    """Set up Alexa Devices platform."""

    session = aiohttp_client.async_create_clientsession(hass)
    coordinator = AmazonDevicesCoordinator(hass, entry, session)

    await coordinator.async_config_entry_first_refresh()

    for sync_call in (
        coordinator.sync_todo_list_items,
        coordinator.sync_history_state,
    ):
        await _async_initial_sync(sync_call)

    async def _on_http2_reauth_required() -> None:
        entry.async_start_reauth(hass)

    # AVS allows one directives stream per HTTP/2 connection, so a shared
    # client would make multiple accounts close each other's stream.
    alexa_httpx_client = httpx_client.create_async_httpx_client(
        hass,
        alpn_protocols=SSL_ALPN_HTTP11_HTTP2,
    )

    await coordinator.api.start_http2_processing(
        alexa_httpx_client,
        on_reauth_required=_on_http2_reauth_required,
    )

    async def _async_stop_http2(_event: Event | None = None) -> None:
        """Stop HTTP/2 processing on entry unload or HA shutdown."""
        await coordinator.api.stop_http2_processing()

    entry.async_on_unload(_async_stop_http2)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop_http2)
    )

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


def _move_legacy_settings(hass: HomeAssistant) -> None:
    """Move library settings from the config root into .storage."""
    old_dir = Path(hass.config.path(DOMAIN))
    old_file = old_dir / SETTINGS_FILENAME
    new_file = Path(hass.config.path(STORAGE_DIR, DOMAIN, SETTINGS_FILENAME))
    if not old_file.exists() or new_file.exists():
        return
    new_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        old_file.replace(new_file)
    except FileNotFoundError:
        if new_file.exists():
            return
        raise
    # Only removed when empty, debug dumps may still be there
    with suppress(OSError):
        old_dir.rmdir()


async def async_migrate_entry(hass: HomeAssistant, entry: AmazonConfigEntry) -> None:
    """Migrate old entry."""

    if entry.version == 1 and entry.minor_version < 3:
        LOGGER.debug("Migrating from version %s.%s", entry.version, entry.minor_version)

        new_data = entry.data.copy()
        if CONF_SITE in new_data:
            # Site in data (wrong place), just move to login data
            new_data[CONF_LOGIN_DATA][CONF_SITE] = new_data.pop(CONF_SITE)
        elif CONF_SITE not in new_data[CONF_LOGIN_DATA]:
            # Convert country in domain
            country = new_data[CONF_COUNTRY].lower()
            domain = COUNTRY_DOMAINS.get(country, country)
            new_data[CONF_LOGIN_DATA][CONF_SITE] = f"https://www.amazon.{domain}"

        hass.config_entries.async_update_entry(
            entry, data=new_data, version=1, minor_version=3
        )

        LOGGER.info(
            "Migration to version %s.%s successful", entry.version, entry.minor_version
        )

    if entry.version == 1 and entry.minor_version < 4:
        await hass.async_add_executor_job(_move_legacy_settings, hass)
        hass.config_entries.async_update_entry(entry, version=1, minor_version=4)


async def async_unload_entry(hass: HomeAssistant, entry: AmazonConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
