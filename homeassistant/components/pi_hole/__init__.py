"""The pi_hole component."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Literal

from hole import Hole
from hole.exceptions import HoleError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_API_VERSION,
    CONF_HOST,
    CONF_LOCATION,
    CONF_NAME,
    CONF_SSL,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_STATISTICS_ONLY, DOMAIN, MIN_TIME_BETWEEN_UPDATES

_LOGGER = logging.getLogger(__name__)


PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]

type PiHoleConfigEntry = ConfigEntry[PiHoleData]


@dataclass
class PiHoleData:
    """Runtime data definition."""

    api: Hole
    coordinator: DataUpdateCoordinator[None]


async def async_setup_entry(hass: HomeAssistant, entry: PiHoleConfigEntry) -> bool:
    """Set up Pi-hole entry."""
    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]
    use_tls = entry.data[CONF_SSL]
    verify_tls = entry.data[CONF_VERIFY_SSL]
    location = entry.data[CONF_LOCATION]
    api_key = entry.data.get(CONF_API_KEY, "")
    version = entry.data.get(CONF_API_VERSION)

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

    if version is None:
        _LOGGER.debug(
            "No API version specified, determining Pi-hole API version for %s", host
        )
        version = await determine_api_version(hass, dict(entry.data))
        _LOGGER.debug("Pi-hole API version determined: %s", version)
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_API_VERSION: version}
        )
    session = async_get_clientsession(hass, verify_tls)
    hole_kwargs = {
        "host": host,
        "session": session,
        "location": location,
        "version": version,
    }
    if version == 5:
        hole_kwargs["tls"] = use_tls
        hole_kwargs["api_token"] = api_key
    if version == 6:
        hole_kwargs["protocol"] = "https" if use_tls else "http"
        hole_kwargs["password"] = api_key
    api = Hole(**hole_kwargs)

    async def async_update_data() -> None:
        """Fetch data from API endpoint."""
        try:
            await api.get_data()
            await api.get_versions()
        except HoleError as err:
            raise UpdateFailed(f"Failed to communicate with API: {err}") from err
        if not isinstance(api.data, dict):
            raise ConfigEntryAuthFailed

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=name,
        update_method=async_update_data,
        update_interval=MIN_TIME_BETWEEN_UPDATES,
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = PiHoleData(api, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Pi-hole entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def determine_api_version(
    hass: HomeAssistant, entry: dict[str, Any]
) -> Literal[5, 6]:
    """Determine the API version of the Pi-hole instance without requiring authentication.

    Neither API v5 or v6 provides an endpoint to check the version without authentication.
    Version 6 provides other enddpoints that do not require authentication, so we can use those to determine the version
    version 5 returns an empty list in response to unauthenticated requests.
    Because we are using endpoints that are not designed for this purpose, we should log liberally to help with debugging.
    """
    session = async_get_clientsession(hass, entry[CONF_VERIFY_SSL])
    holeV6 = Hole(
        host=entry[CONF_HOST],
        session=session,
        location=entry[CONF_LOCATION],
        protocol="https" if entry[CONF_SSL] else "http",
        password="wrong_password",
        version=6,
    )
    try:
        await holeV6.authenticate()
    except HoleError as ex_v6:
        if str(ex_v6) == "Authentication failed: Invalid password":
            _LOGGER.debug(
                "Success connecting to Pi-hole at %s without auth, API version is : %s",
                holeV6.base_url,
                6,
            )
            return 6
        _LOGGER.debug(
            "Connection to %s failed: %s, trying API version 5", holeV6.base_url, ex_v6
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.error(
            "Unexpected error connecting to Pi-hole v6 API at %s: %s. Trying version 5 API",
            holeV6.base_url,
            err,
        )

    holeV5 = Hole(
        host=entry[CONF_HOST],
        session=session,
        location=entry[CONF_LOCATION],
        tls=entry[CONF_SSL],
        verify_tls=entry[CONF_VERIFY_SSL],
        api_token="wrong_token",
        version=5,
    )
    try:
        await holeV5.get_data()
        if holeV5.data == []:
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
    except Exception as err:  # noqa: BLE001
        _LOGGER.error(
            "Failed to connect to Pi-hole v5 API at %s: %s", holeV5.base_url, err
        )
    _LOGGER.debug(
        "Could not determine pi-hole API version at: %s",
        holeV6.base_url,
    )
    raise HoleError("Could not determine Pi-hole API version")
