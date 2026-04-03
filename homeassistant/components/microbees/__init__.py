"""The microBees integration."""

from dataclasses import dataclass
from http import HTTPStatus
import logging

import aiohttp
from microBeesPy import MicroBees

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, PLATFORMS
from .coordinator import MicroBeesUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


type MicroBeesConfigEntry = ConfigEntry[HomeAssistantMicroBeesData]


@dataclass(frozen=True, kw_only=True)
class HomeAssistantMicroBeesData:
    """Microbees data stored in the config entry runtime_data."""

    connector: MicroBees
    coordinator: MicroBeesUpdateCoordinator
    session: config_entry_oauth2_flow.OAuth2Session


async def async_migrate_entry(hass: HomeAssistant, entry: MicroBeesConfigEntry) -> bool:
    """Migrate entry."""
    _LOGGER.debug("Migrating from version %s.%s", entry.version, entry.minor_version)

    if entry.version == 1:
        # 1 -> 1.2: Unique ID from integer to string
        if entry.minor_version == 1:
            minor_version = 2
            hass.config_entries.async_update_entry(
                entry, unique_id=str(entry.unique_id), minor_version=minor_version
            )

    _LOGGER.debug("Migration successful")

    return True


async def async_setup_entry(hass: HomeAssistant, entry: MicroBeesConfigEntry) -> bool:
    """Set up microBees from a config entry."""
    try:
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )
    except config_entry_oauth2_flow.ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_implementation_unavailable",
        ) from err

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientResponseError as ex:
        if ex.status in (
            HTTPStatus.BAD_REQUEST,
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        ):
            raise ConfigEntryAuthFailed("Token not valid, trigger renewal") from ex
        raise ConfigEntryNotReady from ex
    microbees = MicroBees(token=session.token[CONF_ACCESS_TOKEN])
    coordinator = MicroBeesUpdateCoordinator(hass, entry, microbees)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = HomeAssistantMicroBeesData(
        connector=microbees,
        coordinator=coordinator,
        session=session,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MicroBeesConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
