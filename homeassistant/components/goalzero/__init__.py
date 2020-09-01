"""The Goal Zero Yeti integration."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from goalzero import GoalZero, exceptions

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    MIN_TIME_BETWEEN_UPDATES,
    DATA_KEY_COORDINATOR,
    DATA_KEY_API,
)

_LOGGER = logging.getLogger(__name__)

GOALZERO_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(CONF_HOST): cv.matches_regex(
                r"\A(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2 \
            [0-4][0-9]|[01]?[0-9][0-9]?)\Z"
            ),
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        },
    )
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [GOALZERO_SCHEMA]))},
    extra=vol.ALLOW_EXTRA,
)


PLATFORMS = ["binary_sensor"]


async def async_setup(hass: HomeAssistant, config):
    """Set up the Goal Zero Yeti component."""

    hass.data[DOMAIN] = {}

    # import
    if DOMAIN in config:
        for conf in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
                )
            )

    return True


async def async_setup_entry(hass, entry):
    """Set up Goal Zero Yeti from a config entry."""
    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]

    _LOGGER.debug("Setting up %s integration with host %s", DOMAIN, host)

    try:
        session = async_get_clientsession(hass)
        api = GoalZero(host, hass.loop, session)
        await api.get_state()
    except exceptions.RequestException as ex:
        _LOGGER.warning("Failed to connect: %s", ex)
        raise ConfigEntryNotReady

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            await api.get_state()
        except exceptions.RequestException as err:
            _LOGGER.warning("Failed to update data from Yeti")
            raise UpdateFailed(f"Failed to communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=name,
        update_method=async_update_data,
        update_interval=MIN_TIME_BETWEEN_UPDATES,
    )
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_KEY_API: api,
        DATA_KEY_COORDINATOR: coordinator,
    }

    for platform in _async_platforms(entry):
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


@callback
def _async_platforms(entry):
    """Return platforms to be loaded / unloaded."""
    return PLATFORMS


class YetiEntity(CoordinatorEntity):
    """Representation of a Goal Zero Yeti entity."""

    def __init__(self, _api, coordinator, name, sensor_name, server_unique_id):
        """Initialize a Goal Zero Yeti entity."""
        super().__init__(coordinator)
        self.api = _api
        self._name = name
        self._server_unique_id = server_unique_id

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:battery"

    @property
    def device_info(self):
        """Return the device information of the entity."""
        return {
            "identifiers": {(DOMAIN, self._server_unique_id)},
            "name": self._name,
            "manufacturer": "Goal Zero",
        }
