"""The Rituals Perfume Genie integration."""

import asyncio
from contextlib import suppress
import logging

from aiohttp import ClientError, ClientResponseError
from pyrituals import Account, AuthenticationException, Diffuser

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ACCOUNT_HASH, DOMAIN, PASSWORD, UPDATE_INTERVAL, USERNAME
from .coordinator import RitualsDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Rituals Perfume Genie from a config entry."""
    _LOGGER.debug("async_setup_entry start (entry_id=%s)", entry.entry_id)
    session = async_get_clientsession(hass)
    with suppress(Exception):
        session.cookie_jar.clear()

    # Require credentials for runtime; if missing, trigger reauth and stop setup
    if USERNAME not in entry.data or PASSWORD not in entry.data:
        await _trigger_reauth(hass, entry)
        return False

    email = entry.data[USERNAME]
    password = entry.data[PASSWORD]

    # ACCOUNT_HASH is kept only for backwards compatibility
    account = Account(
        email=email,
        password=password,
        session=session,
        account_hash=entry.data.get(ACCOUNT_HASH, ""),
    )

    try:
        # Authenticate first so API token/cookies are available for subsequent calls
        await account.authenticate()
        account_devices = await account.get_devices()

    except AuthenticationException:
        # Credentials invalid/expired → start reauth and stop setup until user completes it
        await _trigger_reauth(hass, entry)
        return False

    except ClientResponseError as err:
        _LOGGER.warning(
            "HTTP error during Rituals setup: status=%s, url=%s, headers=%s",
            getattr(err, "status", "?"),
            getattr(err, "request_info", None),
            dict(err.headers or {}),
        )
        raise ConfigEntryNotReady from err

    except ClientError as err:
        _LOGGER.warning("Network error during Rituals setup: %r", err)
        raise ConfigEntryNotReady from err

    # Migrate old unique_ids to the new format
    async_migrate_entities_unique_ids(hass, entry, account_devices)

    # The API provided by Rituals is currently rate limited to 30 requests
    # per hour per IP address. To avoid hitting this limit, we will adjust
    # the polling interval based on the number of diffusers one has.
    update_interval = UPDATE_INTERVAL * max(1, len(account_devices))

    # Create a coordinator for each diffuser
    coordinators = {
        diffuser.hublot: RitualsDataUpdateCoordinator(
            hass, entry, account, diffuser, update_interval
        )
        for diffuser in account_devices
    }

    # Refresh all coordinators
    await asyncio.gather(
        *[
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators.values()
        ]
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


@callback
def async_migrate_entities_unique_ids(
    hass: HomeAssistant, config_entry: ConfigEntry, diffusers: list[Diffuser]
) -> None:
    """Migrate unique_ids in the entity registry to the new format."""
    entity_registry = er.async_get(hass)
    registry_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    conversion: dict[tuple[str, str], str] = {
        (Platform.BINARY_SENSOR, " Battery Charging"): "charging",
        (Platform.NUMBER, " Perfume Amount"): "perfume_amount",
        (Platform.SELECT, " Room Size"): "room_size_square_meter",
        (Platform.SENSOR, " Battery"): "battery_percentage",
        (Platform.SENSOR, " Fill"): "fill",
        (Platform.SENSOR, " Perfume"): "perfume",
        (Platform.SENSOR, " Wifi"): "wifi_percentage",
        (Platform.SWITCH, ""): "is_on",
    }

    for diffuser in diffusers:
        for registry_entry in registry_entries:
            if new_unique_id := conversion.get(
                (
                    registry_entry.domain,
                    registry_entry.unique_id.removeprefix(diffuser.hublot),
                )
            ):
                entity_registry.async_update_entity(
                    registry_entry.entity_id,
                    new_unique_id=f"{diffuser.hublot}-{new_unique_id}",
                )


# Migration helpers for API v2
async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate legacy entries (V1 with account_hash) to V2 (credentials)."""
    data = dict(entry.data)
    if ACCOUNT_HASH in data and (USERNAME not in data or PASSWORD not in data):
        await _trigger_reauth(hass, entry)
        return True
    return True


async def _trigger_reauth(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Start a reauth flow to collect credentials for V2.

    Debounce so we only create one reauth flow per entry.
    """
    domain_data = hass.data.setdefault(DOMAIN, {})
    in_progress: set[str] = domain_data.setdefault("_reauth_in_progress", set())
    if entry.entry_id in in_progress:
        return
    in_progress.add(entry.entry_id)

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
            data={"unique_id": entry.unique_id or ""},
        )
    )
