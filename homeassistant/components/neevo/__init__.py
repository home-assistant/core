"""The Nee-Vo Tank Monitoring integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from aiohttp.client_exceptions import ClientError
from pyneevo import NeeVoApiInterface
from pyneevo.errors import (
    GenericHTTPError,
    InvalidCredentialsError,
    InvalidResponseFormat,
    PyNeeVoError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import API_CLIENT, DOMAIN, TANKS

_LOGGER = logging.getLogger(__name__)

PUSH_UPDATE = "neevo.push_update"
INTERVAL = timedelta(minutes=15)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Nee-Vo component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][API_CLIENT] = {}
    hass.data[DOMAIN][TANKS] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Nee-Vo Tank Monitoring from a config entry."""

    email = config_entry.data[CONF_EMAIL]
    password = config_entry.data[CONF_PASSWORD]

    try:
        api = await NeeVoApiInterface.login(email, password=password)
    except InvalidCredentialsError:
        _LOGGER.error("Invalid credentials provided")
        return False
    except PyNeeVoError as err:
        _LOGGER.error("Config entry failed: %s", err)
        raise ConfigEntryNotReady from err

    try:
        tanks = await api.get_tanks_info()
    except (ClientError, GenericHTTPError, InvalidResponseFormat) as err:
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][API_CLIENT][config_entry.entry_id] = api
    hass.data[DOMAIN][TANKS][config_entry.entry_id] = tanks

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    def update_published():
        """Handle a push update."""
        dispatcher_send(hass, PUSH_UPDATE)

    for _tank in tanks.values():
        _tank.set_update_callback(update_published)

    async def fetch_update(now):
        """Fetch the latest changes from the API."""
        await api.refresh_tanks()

    config_entry.async_on_unload(
        async_track_time_interval(hass, fetch_update, INTERVAL + timedelta(minutes=1))
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN][API_CLIENT].pop(config_entry.entry_id)
        hass.data[DOMAIN][TANKS].pop(config_entry.entry_id)
    return unload_ok


class NeeVoEntity(Entity):
    """Define a base Nee-Vo entity."""

    _attr_should_poll = False

    def __init__(self, neevo):
        """Initialize."""
        self._neevo = neevo
        self._attr_name = neevo.name
        self._attr_unique_id = f"{neevo.id}_{neevo.name}"

    async def async_added_to_hass(self):
        """Subscribe to device events."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, PUSH_UPDATE, self.on_update_received)
        )

    @callback
    def on_update_received(self):
        """Update was pushed from the Nee-Vo API."""
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._neevo.id)},
            manufacturer="OTODATA",
            name=self._neevo.name,
        )
