"""Support for Roku."""
import asyncio
from datetime import timedelta
import logging
from typing import Any, Dict

from rokuecp import Roku, RokuConnectionError, RokuError
from rokuecp.models import Device
import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import ATTR_NAME, CONF_HOST
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import utcnow

from .const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_SOFTWARE_VERSION,
    DOMAIN,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list, [vol.Schema({vol.Required(CONF_HOST): cv.string})]
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [MEDIA_PLAYER_DOMAIN, REMOTE_DOMAIN]
SCAN_INTERVAL = timedelta(seconds=20)
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config: Dict) -> bool:
    """Set up the Roku integration."""
    hass.data.setdefault(DOMAIN, {})

    if DOMAIN in config:
        for entry_config in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry_config,
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up Roku from a config entry."""
    coordinator = RokuDataUpdateCoordinator(hass, host=entry.data[CONF_HOST])
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = coordinator

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
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


def roku_exception_handler(func):
    """Decorate Roku calls to handle Roku exceptions."""

    async def handler(self, *args, **kwargs):
        try:
            await func(self, *args, **kwargs)
        except RokuConnectionError as error:
            if self.available:
                _LOGGER.error("Error communicating with API: %s", error)
        except RokuError as error:
            if self.available:
                _LOGGER.error("Invalid response from API: %s", error)

    return handler


class RokuDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Roku data."""

    def __init__(
        self, hass: HomeAssistantType, *, host: str,
    ):
        """Initialize global Roku data updater."""
        self.roku = Roku(host=host, session=async_get_clientsession(hass))

        self.full_update_interval = timedelta(minutes=15)
        self.last_full_update = None

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> Device:
        """Fetch data from Roku."""
        full_update = self.last_full_update is None or utcnow() >= (
            self.last_full_update + self.full_update_interval
        )

        try:
            data = await self.roku.update(full_update=full_update)

            if full_update:
                self.last_full_update = utcnow()

            return data
        except RokuError as error:
            raise UpdateFailed(f"Invalid response from API: {error}")


class RokuEntity(Entity):
    """Defines a base Roku entity."""

    def __init__(
        self, *, device_id: str, name: str, coordinator: RokuDataUpdateCoordinator
    ) -> None:
        """Initialize the Roku entity."""
        self._device_id = device_id
        self._name = name
        self.coordinator = coordinator

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """Return the polling requirement of the entity."""
        return False

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        """Update an Roku entity."""
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this Roku device."""
        if self._device_id is None:
            return None

        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._device_id)},
            ATTR_NAME: self.name,
            ATTR_MANUFACTURER: self.coordinator.data.info.brand,
            ATTR_MODEL: self.coordinator.data.info.model_name,
            ATTR_SOFTWARE_VERSION: self.coordinator.data.info.version,
        }
