"""The twitch integration."""
import asyncio
from datetime import timedelta
import logging
from typing import Any, Dict, Optional, Union

import twitch as Twitch
from twitch import Helix
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DATA_TWITCH_CLIENT, DATA_TWITCH_UPDATED, DATA_USER, DOMAIN

_LOGGER = logging.getLogger(__name__)


DATA_TWITCH = DOMAIN

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["sensor"]

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): vol.Schema({vol.Required(CONF_CLIENT_ID): cv.string})},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the twitch component."""
    hass.data[DATA_TWITCH_CLIENT] = Twitch.Helix(
        config[DOMAIN].get(CONF_CLIENT_ID),
        use_cache=True,
        cache_duration=timedelta(minutes=5),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up twitch from a config entry."""

    # Get twitch instance for this entry
    twitch = hass.data[DATA_TWITCH_CLIENT]

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {DATA_TWITCH_CLIENT: twitch}

    # Get user
    user = twitch.user(entry.data[DATA_USER])

    # For backwards compat, set unique ID
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=user.id)

    # Set up all platforms for this device/entry.
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
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


class TwitchEntity(Entity):
    """Defines a base Twitch entity."""

    def __init__(
        self,
        entry_id: str,
        twitch: Helix,
        user: str,
        name: str,
        icon: str,
        enabled_default: bool = True,
    ) -> None:
        """Initialize the Twitch entity."""
        self._attributes: Dict[str, Union[str, int, float]] = {}
        self._available = True
        self._enabled_default = enabled_default
        self._entry_id = entry_id
        self._icon = icon
        self._name = name
        self._unsub_dispatcher = None
        self.twitch = twitch

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default

    @property
    def should_poll(self) -> bool:
        """Return the polling requirement of the entity."""
        return True

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        return self._attributes

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, DATA_TWITCH_UPDATED, self._schedule_immediate_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect from update signal."""
        self._unsub_dispatcher()

    @callback
    def _schedule_immediate_update(self, entry_id: str) -> None:
        """Schedule an immediate update of the entity."""
        if entry_id == self._entry_id:
            self.async_schedule_update_ha_state(True)

    async def async_update(self) -> None:
        """Update Twitch entity."""
        if not self.enabled:
            return

        if self.twitch is None:
            self._available = False
            return

        self._available = True
        await self._twitch_update()

    async def _twitch_update(self) -> None:
        """Update Twitch entity."""
        raise NotImplementedError()
