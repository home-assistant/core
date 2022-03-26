"""Support to check for available updates."""
import asyncio
from datetime import timedelta
import logging

import async_timeout
from awesomeversion import AwesomeVersion
import voluptuous as vol

from homeassistant.components import hassio
from homeassistant.const import Platform, __version__ as current_version
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery, update_coordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

ATTR_RELEASE_NOTES = "release_notes"
ATTR_NEWEST_VERSION = "newest_version"

CONF_REPORTING = "reporting"
CONF_COMPONENT_REPORTING = "include_used_components"

DOMAIN = "updater"

UPDATER_URL = "https://www.home-assistant.io/version.json"


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            vol.Optional(CONF_REPORTING): cv.boolean,
            vol.Optional(CONF_COMPONENT_REPORTING): cv.boolean,
        }
    },
    extra=vol.ALLOW_EXTRA,
)

RESPONSE_SCHEMA = vol.Schema(
    {vol.Required("current_version"): cv.string, vol.Required("release_notes"): cv.url},
    extra=vol.REMOVE_EXTRA,
)


class Updater:
    """Updater class for data exchange."""

    def __init__(
        self, update_available: bool, newest_version: str, release_notes: str
    ) -> None:
        """Initialize attributes."""
        self.update_available = update_available
        self.release_notes = release_notes
        self.newest_version = newest_version


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the updater component."""
    _LOGGER.warning(
        "The updater integration has been deprecated and will be removed in 2022.5, "
        "please remove it from your configuration"
    )

    async def check_new_version() -> Updater:
        """Check if a new version is available and report if one is."""
        # Skip on dev
        if "dev" in current_version:
            return Updater(False, "", "")

        newest, release_notes = await get_newest_version(hass)

        _LOGGER.debug("Fetched version %s: %s", newest, release_notes)

        # Load data from Supervisor
        if hassio.is_hassio(hass):
            core_info = hassio.get_core_info(hass)
            newest = core_info["version_latest"]

        # Validate version
        update_available = False
        if AwesomeVersion(newest) > AwesomeVersion(current_version):
            _LOGGER.debug(
                "The latest available version of Home Assistant is %s", newest
            )
            update_available = True
        elif AwesomeVersion(newest) == AwesomeVersion(current_version):
            _LOGGER.debug(
                "You are on the latest version (%s) of Home Assistant", newest
            )
        elif AwesomeVersion(newest) < AwesomeVersion(current_version):
            _LOGGER.debug(
                "Local version (%s) is newer than the latest available version (%s)",
                current_version,
                newest,
            )

        _LOGGER.debug("Update available: %s", update_available)

        return Updater(update_available, newest, release_notes)

    coordinator = hass.data[DOMAIN] = update_coordinator.DataUpdateCoordinator[Updater](
        hass,
        _LOGGER,
        name="Home Assistant update",
        update_method=check_new_version,
        update_interval=timedelta(days=1),
    )

    # This can take up to 15s which can delay startup
    asyncio.create_task(coordinator.async_refresh())

    hass.async_create_task(
        discovery.async_load_platform(hass, Platform.BINARY_SENSOR, DOMAIN, {}, config)
    )

    return True


async def get_newest_version(hass):
    """Get the newest Home Assistant version."""
    session = async_get_clientsession(hass)

    async with async_timeout.timeout(30):
        req = await session.get(UPDATER_URL)

    try:
        res = await req.json()
    except ValueError as err:
        raise update_coordinator.UpdateFailed(
            "Received invalid JSON from Home Assistant Update"
        ) from err

    try:
        res = RESPONSE_SCHEMA(res)
        return res["current_version"], res["release_notes"]
    except vol.Invalid as err:
        raise update_coordinator.UpdateFailed(
            f"Got unexpected response: {err}"
        ) from err
