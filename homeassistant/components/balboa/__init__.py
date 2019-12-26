"""The Balboa Spa integration."""
import asyncio
import logging
import time

from pybalboa import BalboaSpaWifi
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity

from .const import BALBOA_PLATFORMS, DOMAIN

_LOGGER = logging.getLogger(__name__)

BALBOA_CONFIG_SCHEMA = vol.Schema(
    {vol.Required(CONF_HOST): cv.string, vol.Required(CONF_NAME): cv.string}
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [BALBOA_CONFIG_SCHEMA])}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Configure the Balboa Spa component using flow only."""
    hass.data[DOMAIN] = {}

    if DOMAIN in config:
        for entry in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                )
            )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Balboa Spa from a config entry."""
    host = entry.data[CONF_HOST]

    _LOGGER.debug("Attempting to connect to %s", host)
    spa = BalboaSpaWifi(host)
    hass.data[DOMAIN][entry.entry_id] = spa

    connected = await spa.connect()
    if not connected:
        _LOGGER.error("Failed to connect to spa at %s", host)
        return False

    # send config requests, and then listen until we are configured.
    await spa.send_config_req()
    await spa.send_panel_req(0, 1)
    # configured = await spa.listen_until_configured()

    _LOGGER.debug("Starting listener and monitor tasks.")
    hass.loop.create_task(spa.listen())
    hass.loop.create_task(spa.check_connection_status())
    await spa.spa_configured()

    # At this point we have a configured spa.
    forward_setup = hass.config_entries.async_forward_entry_setup
    for component in BALBOA_PLATFORMS:
        hass.async_create_task(forward_setup(entry, component))

    async def _async_balboa_update_cb():
        """Primary update callback called from pybalboa."""
        _LOGGER.debug("Primary update callback triggered")
        async_dispatcher_send(hass, DOMAIN)

    spa.new_data_cb = _async_balboa_update_cb

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""

    spa = hass.data[DOMAIN][entry.entry_id]
    spa.disconnect()

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in BALBOA_PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class BalboaEntity(Entity):
    """Abstract class for all Balboa platforms.

    Once you connect to the spa's port, it continuously sends data (at a rate
    of about 5 per second!).  The API updates the internal states of things
    from this stream, and all we have to do is read the values out of the
    accessors.
    """

    def __init__(self, hass, client, name):
        """Initialize the spa."""
        self.hass = hass
        self._client = client
        self._name = name

    async def async_added_to_hass(self) -> None:
        """Set up a listener for the entity."""
        async_dispatcher_connect(self.hass, DOMAIN, self._update_callback)

    @callback
    def _update_callback(self) -> None:
        """Call from dispatcher when state changes."""
        _LOGGER.debug("Updating spa state with new data. %s", self._name)
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def should_poll(self) -> bool:
        """Return false as entities should not be polled."""
        return False

    @property
    def unique_id(self):
        """Set unique_id for this entity."""
        return f'{self._name}-{self._client.get_macaddr().replace(":","")[-6:]}'

    @property
    def assumed_state(self) -> bool:
        """Return whether the state is based on actual reading from device."""
        if (self._client.lastupd + 5 * 60) < time.time():
            return True
        return False

    @property
    def available(self) -> bool:
        """Return whether the entity is available or not."""
        return self._client.connected
