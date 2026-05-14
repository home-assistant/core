"""The pi_hole component."""

import asyncio
import logging
from typing import Any, Literal

import aiohttp
from aiohttp import DummyCookieJar
from hole import Hole, HoleV5, HoleV6
from hole.exceptions import HoleConnectionError, HoleError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_LOCATION,
    CONF_SSL,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_CLOSE,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)

from .const import CONF_STATISTICS_ONLY, DOMAIN
from .coordinator import PiHoleConfigEntry, PiHoleData, PiHoleUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

DATA_V6_CLIENTSESSIONS = f"{DOMAIN}_v6_clientsessions"


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
) -> HoleV5 | HoleV6:
    """Create a pi-hole API object by API version number. Once V5 is deprecated this function can be removed."""

    if password is None:
        password = entry.get(CONF_API_KEY, "")
    if version == 6:
        session = _async_get_v6_session(hass, entry[CONF_VERIFY_SSL])
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
def _async_get_v6_session(
    hass: HomeAssistant, verify_ssl: bool
) -> aiohttp.ClientSession:
    """Get a session with an isolated cookie jar for the Pi-hole v6 API.

    The session opts out of the auto-cleanup tied to the current config entry,
    since the cache is shared across entries — otherwise the first entry to
    unload would detach a session still in use by the others. Lifetime is
    bound to Home Assistant shutdown instead.
    """
    sessions: dict[bool, aiohttp.ClientSession] = hass.data.setdefault(
        DATA_V6_CLIENTSESSIONS, {}
    )
    session = sessions.get(verify_ssl)
    if session is None or session.closed:
        session = async_create_clientsession(
            hass, verify_ssl, auto_cleanup=False, cookie_jar=DummyCookieJar()
        )
        sessions[verify_ssl] = session

        @callback
        def _close(_event: Event) -> None:
            session.detach()
            sessions.pop(verify_ssl, None)

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _close)
    return session


async def _async_is_v6_api(hass: HomeAssistant, entry: dict[str, Any]) -> bool:
    """Check if the Pi-hole instance exposes the v6 API."""
    protocol = "https" if entry.get(CONF_SSL) else "http"
    session = _async_get_v6_session(hass, entry[CONF_VERIFY_SSL])
    url = f"{protocol}://{entry[CONF_HOST]}/api/info/version"

    async with asyncio.timeout(5):
        async with session.get(url) as response:
            try:
                data: Any = await response.json()
            except aiohttp.ContentTypeError, ValueError:
                return False

            if not isinstance(data, dict):
                return False

            if response.status == 200:
                return isinstance(data.get("version"), dict)

            if response.status == 401:
                error = data.get("error")
                return isinstance(error, dict) and error.get("key") == "unauthorized"

    return False


async def determine_api_version(
    hass: HomeAssistant, entry: dict[str, Any]
) -> Literal[5, 6]:
    """Determine the API version of the Pi-hole instance without requiring authentication.

    Version 6 returns either version data or a distinct unauthorized error from
    /api/info/version, so we can use that endpoint to determine the version.
    Version 5 returns an empty list in response to unauthenticated requests.
    Because we are using endpoints that are not designed for this purpose, we should log liberally to help with debugging.
    """

    try:
        if await _async_is_v6_api(hass, entry):
            _LOGGER.debug(
                "Response from v6 API without auth, Pi-hole API version 6 probably detected at %s",
                entry[CONF_HOST],
            )
            return 6
    except (TimeoutError, aiohttp.ClientError) as err:
        _LOGGER.error(
            "Unexpected error connecting to Pi-hole v6 API at %s: %s. Trying version 5 API",
            entry[CONF_HOST],
            err,
        )

    holeV5 = api_by_version(hass, entry, 5, password="wrong_token")
    try:
        await holeV5.get_data()

    except HoleConnectionError as err:
        _LOGGER.error(
            "Failed to connect to Pi-hole v5 API at %s: %s", holeV5.base_url, err
        )
    else:
        # V5 API returns [] to unauthenticated requests
        if not holeV5.data:
            _LOGGER.debug(
                "Response '[]' from API without auth, pihole API version 5 probably detected at %s",
                holeV5.base_url,
            )
            return 5
        _LOGGER.debug(
            "Unexpected response from Pi-hole API at %s: %s",
            holeV5.base_url,
            str(holeV5.data),
        )
    _LOGGER.debug(
        "Could not determine pi-hole API version at: %s",
        entry[CONF_HOST],
    )
    raise HoleError("Could not determine Pi-hole API version")
