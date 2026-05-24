"""The Vistapool integration."""

from dataclasses import dataclass, field
import logging

from aioaquarite import AquariteAuth, AquariteClient, AquariteError, AuthenticationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import VistapoolDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


@dataclass
class VistapoolData:
    """Runtime data for a Vistapool account (holds one coordinator per pool)."""

    auth: AquariteAuth
    api: AquariteClient
    coordinators: dict[str, VistapoolDataUpdateCoordinator] = field(
        default_factory=dict
    )


type VistapoolConfigEntry = ConfigEntry[VistapoolData]


async def async_setup_entry(hass: HomeAssistant, entry: VistapoolConfigEntry) -> bool:
    """Set up Vistapool from a config entry.

    One config entry represents a Hayward account; the account can contain
    multiple pools, each exposed as a separate device.
    """
    user_config = entry.data
    session = async_get_clientsession(hass)

    auth = AquariteAuth(session, user_config[CONF_USERNAME], user_config[CONF_PASSWORD])
    try:
        await auth.authenticate()
    except AuthenticationError as exc:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_credentials",
        ) from exc
    except AquariteError as exc:
        raise ConfigEntryNotReady from exc

    api = AquariteClient(auth)
    try:
        pools = await api.get_pools()
    except AquariteError as exc:
        raise ConfigEntryNotReady from exc

    if not pools:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="no_pools",
        )

    data = VistapoolData(auth=auth, api=api)

    try:
        for pool_id, pool_name in pools.items():
            coordinator = VistapoolDataUpdateCoordinator(
                hass, entry, auth, api, pool_id, pool_name
            )
            data.coordinators[pool_id] = coordinator
            await coordinator.async_config_entry_first_refresh()
            try:
                await coordinator.subscribe()
            except AquariteError as exc:
                raise ConfigEntryNotReady from exc
            entry.async_on_unload(coordinator.async_shutdown)
    except Exception:
        for coordinator in data.coordinators.values():
            await coordinator.async_shutdown()
        raise

    entry.runtime_data = data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VistapoolConfigEntry) -> bool:
    """Unload Vistapool config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
