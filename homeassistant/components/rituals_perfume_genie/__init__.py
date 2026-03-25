"""The Rituals Perfume Genie integration."""

import asyncio
import logging

from aiohttp import ClientError, ClientResponseError
from pyrituals import Account, AuthenticationException, Diffuser

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ACCOUNT_HASH, DOMAIN, UPDATE_INTERVAL
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
    # Initiate reauth for old config entries which don't have username / password in the entry data
    if CONF_EMAIL not in entry.data or CONF_PASSWORD not in entry.data:
        raise ConfigEntryAuthFailed("Missing credentials")

    session = async_get_clientsession(hass)

    account = Account(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        session=session,
    )

    try:
        # Authenticate first so API token/cookies are available for subsequent calls
        await account.authenticate()
        account_devices = await account.get_devices()

    except AuthenticationException as err:
        # Credentials invalid/expired -> raise AuthFailed to trigger reauth flow

        raise ConfigEntryAuthFailed(err) from err

    except ClientResponseError as err:
        _LOGGER.debug(
            "HTTP error during Rituals setup: status=%s, url=%s, headers=%s",
            err.status,
            err.request_info,
            dict(err.headers or {}),
        )
        raise ConfigEntryNotReady from err

    except ClientError as err:
        raise ConfigEntryNotReady from err

    # Migrate old unique_ids to the new format
    async_migrate_entities_unique_ids(hass, entry, account_devices)

    # The API provided by Rituals is currently rate limited to 30 requests
    # per hour per IP address. To avoid hitting this limit, we will adjust
    # the polling interval based on the number of diffusers one has.
    update_interval = UPDATE_INTERVAL * len(account_devices)

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
    """Migrate config entry to version 2: drop legacy ACCOUNT_HASH and bump version."""
    if entry.version < 2:
        data = dict(entry.data)
        data.pop(ACCOUNT_HASH, None)
        hass.config_entries.async_update_entry(entry, data=data, version=2)
        return True
    return True
