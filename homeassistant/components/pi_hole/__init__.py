"""The pi_hole component."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from typing import Any, Literal

import aiohttp
from aiohttp import DummyCookieJar
from hole import Hole, HoleV5, HoleV6
from hole.exceptions import HoleAuthenticationError, HoleConnectionError, HoleError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_LOCATION,
    CONF_SSL,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)

from .const import CONF_STATISTICS_ONLY, DOMAIN
from .coordinator import PiHoleConfigEntry, PiHoleData, PiHoleUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: PiHoleConfigEntry) -> bool:
    """Set up Pi-hole entry."""
    host = entry.data[CONF_HOST]

    # remove obsolet CONF_STATISTICS_ONLY from entry.data
    if CONF_STATISTICS_ONLY in entry.data:
        entry_data = entry.data.copy()
        entry_data.pop(CONF_STATISTICS_ONLY)
        hass.config_entries.async_update_entry(entry, data=entry_data)

    _LOGGER.debug("Setting up %s integration with host %s", DOMAIN, host)

    name_to_key = {
        "Core Update Available": "core_update_available",
        "Web Update Available": "web_update_available",
        "FTL Update Available": "ftl_update_available",
        "Status": "status",
        "Ads Blocked Today": "ads_blocked_today",
        "Ads Percentage Blocked Today": "ads_percentage_today",
        "Seen Clients": "clients_ever_seen",
        "DNS Queries Today": "dns_queries_today",
        "Domains Blocked": "domains_being_blocked",
        "DNS Queries Cached": "queries_cached",
        "DNS Queries Forwarded": "queries_forwarded",
        "DNS Unique Clients": "unique_clients",
        "DNS Unique Domains": "unique_domains",
    }

    @callback
    def update_unique_id(
        entity_entry: er.RegistryEntry,
    ) -> dict[str, str] | None:
        """Update unique ID of entity entry."""
        unique_id_parts = entity_entry.unique_id.split("/")
        if len(unique_id_parts) == 2 and unique_id_parts[1] in name_to_key:
            name = unique_id_parts[1]
            new_unique_id = entity_entry.unique_id.replace(name, name_to_key[name])
            _LOGGER.debug("Migrate %s to %s", entity_entry.unique_id, new_unique_id)
            return {"new_unique_id": new_unique_id}

        return None

    await er.async_migrate_entries(hass, entry.entry_id, update_unique_id)

    _LOGGER.debug("Determining Pi-hole API version for %s", host)
    version = await determine_api_version(hass, dict(entry.data))
    _LOGGER.debug("Pi-hole API version determined: %s", version)

    # Once API version 5 is deprecated we should instantiate Hole directly
    api = api_by_version(hass, dict(entry.data), version)

    coordinator = PiHoleUpdateCoordinator(hass, api, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = PiHoleData(api, coordinator, version)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Pi-hole entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def api_by_version(
    hass: HomeAssistant,
    entry: dict[str, Any],
    version: int,
    password: str | None = None,
    session: aiohttp.ClientSession | None = None,
) -> HoleV5 | HoleV6:
    """Create a pi-hole API object by API version number.

    Once V5 is deprecated this function can be removed.
    """

    if password is None:
        password = entry.get(CONF_API_KEY, "")
    if version == 6:
        session = session or _async_create_v6_session(hass, entry[CONF_VERIFY_SSL])
    else:
        session = async_get_clientsession(hass, entry[CONF_VERIFY_SSL])
    hole_kwargs = {
        "host": entry[CONF_HOST],
        "session": session,
        "location": entry[CONF_LOCATION],
        "verify_tls": entry[CONF_VERIFY_SSL],
        "version": version,
    }
    if version == 5:
        hole_kwargs["tls"] = entry.get(CONF_SSL)
        hole_kwargs["api_token"] = password
    elif version == 6:
        hole_kwargs["protocol"] = "https" if entry.get(CONF_SSL) else "http"
        hole_kwargs["password"] = password

    return Hole(**hole_kwargs)


@callback
def _async_create_v6_session(
    hass: HomeAssistant, verify_ssl: bool, *, auto_cleanup: bool = True
) -> aiohttp.ClientSession:
    """Create a session with an isolated cookie jar for the Pi-hole v6 API."""
    return async_create_clientsession(
        hass,
        verify_ssl,
        auto_cleanup=auto_cleanup,
        cookie_jar=DummyCookieJar(),
    )


@asynccontextmanager
async def _async_v6_session(
    hass: HomeAssistant, verify_ssl: bool
) -> AsyncIterator[aiohttp.ClientSession]:
    """Yield a short-lived isolated session for one-shot Pi-hole v6 requests."""
    session = _async_create_v6_session(hass, verify_ssl, auto_cleanup=False)
    try:
        yield session
    finally:
        session.detach()


async def _async_v6_api_authentication_required(
    hass: HomeAssistant, entry: dict[str, Any]
) -> bool | None:
    """Return if the v6 API requires auth, or None when v6 is not detected."""
    async with _async_v6_session(hass, entry[CONF_VERIFY_SSL]) as session:
        hole_v6 = api_by_version(hass, entry, 6, password="", session=session)
        try:
            await hole_v6.get_versions()
        except HoleConnectionError:
            raise
        except HoleAuthenticationError:
            return True
        except HoleError:
            return None

        return False


async def determine_api_version(
    hass: HomeAssistant, entry: dict[str, Any]
) -> Literal[5, 6]:
    """Determine the API version of the Pi-hole instance without authentication.

    Version 6 returns either version data or a distinct unauthorized error from
    /api/info/version, so we can use that endpoint to determine the version.
    Version 5 returns an empty list in response to unauthenticated requests.
    Because we are using endpoints that are not designed for this purpose, we should
    log liberally to help with debugging.
    """

    try:
        if await _async_v6_api_authentication_required(hass, entry) is not None:
            _LOGGER.debug(
                "Response from v6 API without auth, Pi-hole API version 6 probably"
                " detected at %s",
                entry[CONF_HOST],
            )
            return 6
    except HoleConnectionError as err:
        _LOGGER.error(
            "Unexpected error connecting to Pi-hole v6 API at %s: %s. Trying version"
            " 5 API",
            entry[CONF_HOST],
            err,
        )

    hole_v5 = api_by_version(hass, entry, 5, password="wrong_token")
    try:
        await hole_v5.get_data()

    except HoleConnectionError as err:
        _LOGGER.error(
            "Failed to connect to Pi-hole v5 API at %s: %s", hole_v5.base_url, err
        )
    else:
        # V5 API returns [] to unauthenticated requests
        if not hole_v5.data:
            _LOGGER.debug(
                "Response '[]' from API without auth,"
                " pihole API version 5 probably"
                " detected at %s",
                hole_v5.base_url,
            )
            return 5
        _LOGGER.debug(
            "Unexpected response from Pi-hole API at %s: %s",
            hole_v5.base_url,
            str(hole_v5.data),
        )
    _LOGGER.debug(
        "Could not determine pi-hole API version at: %s",
        entry[CONF_HOST],
    )
    raise HoleError("Could not determine Pi-hole API version")
