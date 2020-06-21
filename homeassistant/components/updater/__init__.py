"""Support to check for available updates."""
import asyncio
from datetime import timedelta
from distutils.version import StrictVersion
import logging

import async_timeout
from distro import linux_distribution  # pylint: disable=import-error
import voluptuous as vol

from homeassistant.const import __version__ as current_version
from homeassistant.helpers import discovery, update_coordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_RELEASE_NOTES = "release_notes"
ATTR_NEWEST_VERSION = "newest_version"

CONF_REPORTING = "reporting"
CONF_COMPONENT_REPORTING = "include_used_components"

DOMAIN = "updater"

UPDATER_URL = "https://updater.home-assistant.io/"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            vol.Optional(CONF_REPORTING, default=True): cv.boolean,
            vol.Optional(CONF_COMPONENT_REPORTING, default=False): cv.boolean,
        }
    },
    extra=vol.ALLOW_EXTRA,
)

RESPONSE_SCHEMA = vol.Schema(
    {vol.Required("version"): cv.string, vol.Required("release-notes"): cv.url}
)


class Updater:
    """Updater class for data exchange."""

    def __init__(self, update_available: bool, newest_version: str, release_notes: str):
        """Initialize attributes."""
        self.update_available = update_available
        self.release_notes = release_notes
        self.newest_version = newest_version


async def async_setup(hass, config):
    """Set up the updater component."""
    if "dev" in current_version:
        # This component only makes sense in release versions
        _LOGGER.info("Running on 'dev', only analytics will be submitted")

    conf = config.get(DOMAIN, {})
    if conf.get(CONF_REPORTING):
        huuid = await hass.helpers.instance_id.async_get()
    else:
        huuid = None

    include_components = conf.get(CONF_COMPONENT_REPORTING)

    async def check_new_version():
        """Check if a new version is available and report if one is."""
        newest, release_notes = await get_newest_version(
            hass, huuid, include_components
        )

        _LOGGER.debug("Fetched version %s: %s", newest, release_notes)

        # Skip on dev
        if "dev" in current_version:
            return Updater(False, "", "")

        # Load data from supervisor on Hass.io
        if hass.components.hassio.is_hassio():
            newest = hass.components.hassio.get_homeassistant_version()

        # Validate version
        update_available = False
        if StrictVersion(newest) > StrictVersion(current_version):
            _LOGGER.debug(
                "The latest available version of Home Assistant is %s", newest
            )
            update_available = True
        elif StrictVersion(newest) == StrictVersion(current_version):
            _LOGGER.debug(
                "You are on the latest version (%s) of Home Assistant", newest
            )
        elif StrictVersion(newest) < StrictVersion(current_version):
            _LOGGER.debug("Local version is newer than the latest version (%s)", newest)

        _LOGGER.debug("Update available: %s", update_available)

        return Updater(update_available, newest, release_notes)

    coordinator = hass.data[DOMAIN] = update_coordinator.DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Home Assistant update",
        update_method=check_new_version,
        update_interval=timedelta(days=1),
    )

    # This can take up to 15s which can delay startup
    asyncio.create_task(coordinator.async_refresh())

    hass.async_create_task(
        discovery.async_load_platform(hass, "binary_sensor", DOMAIN, {}, config)
    )

    return True


async def get_newest_version(hass, huuid, include_components):
    """Get the newest Home Assistant version."""
    if huuid:
        info_object = await hass.helpers.system_info.async_get_system_info()

        if include_components:
            info_object["components"] = list(hass.config.components)

        linux_dist = await hass.async_add_executor_job(linux_distribution, False)
        info_object["distribution"] = linux_dist[0]
        info_object["os_version"] = linux_dist[1]

        info_object["huuid"] = huuid
    else:
        info_object = {}

    session = async_get_clientsession(hass)

    with async_timeout.timeout(15):
        req = await session.post(UPDATER_URL, json=info_object)

    _LOGGER.info(
        (
            "Submitted analytics to Home Assistant servers. "
            "Information submitted includes %s"
        ),
        info_object,
    )

    try:
        res = await req.json()
    except ValueError:
        raise update_coordinator.UpdateFailed(
            "Received invalid JSON from Home Assistant Update"
        )

    try:
        res = RESPONSE_SCHEMA(res)
        return res["version"], res["release-notes"]
    except vol.Invalid as err:
        raise update_coordinator.UpdateFailed(f"Got unexpected response: {err}")
