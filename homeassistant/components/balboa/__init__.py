"""The Balboa Spa Client integration."""
import asyncio
import time

from pybalboa import BalboaSpaWifi
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, Entity
import homeassistant.util.dt as dt_util

from .const import (
    _LOGGER,
    CONF_SYNC_TIME,
    DEFAULT_SYNC_TIME,
    DOMAIN,
    PLATFORMS,
    SPA,
    UNSUB,
)

BALBOA_CONFIG_SCHEMA = vol.Schema(
    {vol.Required(CONF_HOST): cv.string, vol.Required(CONF_NAME): cv.string}
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [BALBOA_CONFIG_SCHEMA])}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Configure the Balboa Spa Client component using flow only."""
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

    unsub = entry.add_update_listener(update_listener)

    _LOGGER.debug("Attempting to connect to %s", host)
    spa = BalboaSpaWifi(host)
    hass.data[DOMAIN][entry.entry_id] = {SPA: spa, UNSUB: unsub}

    connected = await spa.connect()
    if not connected:
        _LOGGER.error("Failed to connect to spa at %s", host)
        raise ConfigEntryNotReady

    # send config requests, and then listen until we are configured.
    await spa.send_mod_ident_req()
    await spa.send_panel_req(0, 1)

    _LOGGER.debug("Starting listener and monitor tasks")
    hass.loop.create_task(spa.listen())
    await spa.spa_configured()
    hass.loop.create_task(spa.check_connection_status())

    # At this point we have a configured spa.
    forward_setup = hass.config_entries.async_forward_entry_setup
    for component in PLATFORMS:
        hass.async_create_task(forward_setup(entry, component))

    async def _async_balboa_update_cb():
        """Primary update callback called from pybalboa."""
        _LOGGER.debug("Primary update callback triggered")
        async_dispatcher_send(hass, DOMAIN)

    spa.new_data_cb = _async_balboa_update_cb

    # call update_listener on startup
    await update_listener(hass, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""

    _LOGGER.debug("Disconnecting from spa")
    spa = hass.data[DOMAIN][entry.entry_id][SPA]
    await spa.disconnect()

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    hass.data[DOMAIN][entry.entry_id][UNSUB]()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass, entry):
    """Handle options update."""
    if entry.options.get(CONF_SYNC_TIME, DEFAULT_SYNC_TIME):
        _LOGGER.debug("Setting up daily time sync")
        spa = hass.data[DOMAIN][entry.entry_id][SPA]

        async def sync_time():
            while entry.options.get(CONF_SYNC_TIME, DEFAULT_SYNC_TIME):
                _LOGGER.debug("Syncing time with Home Assistant")
                await spa.set_time(
                    time.strptime(str(dt_util.now()), "%Y-%m-%d %H:%M:%S.%f%z")
                )
                await asyncio.sleep(86400)

        hass.loop.create_task(sync_time())


class BalboaEntity(Entity):
    """Abstract class for all Balboa platforms.

    Once you connect to the spa's port, it continuously sends data (at a rate
    of about 5 per second!).  The API updates the internal states of things
    from this stream, and all we have to do is read the values out of the
    accessors.
    """

    _attr_should_poll = False

    def __init__(self, hass, entry, devtype, num=None):
        """Initialize the spa entity."""
        self.hass = hass
        self._client = hass.data[DOMAIN][entry.entry_id][SPA]
        self._device_name = entry.data[CONF_NAME]
        self._type = devtype
        self._num = num
        self._attr_unique_id = f'{self._device_name}-{self._type}{self._num or ""}-{self._client.get_macaddr().replace(":","")[-6:]}'
        self._attr_name = f'{self._device_name}: {self._type}{self._num or ""}'
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._client.get_macaddr())},
            name=self._device_name,
            manufacturer="Balboa Water Group",
            model=self._client.get_model_name(),
            sw_version=self._client.get_ssid(),
            connections={(CONNECTION_NETWORK_MAC, self._client.get_macaddr())},
        )

    async def async_added_to_hass(self) -> None:
        """Set up a listener for the entity."""
        async_dispatcher_connect(self.hass, DOMAIN, self._update_callback)

    @callback
    def _update_callback(self) -> None:
        """Call from dispatcher when state changes."""
        _LOGGER.debug("Updating %s state with new data", self.name)
        self.async_schedule_update_ha_state(force_refresh=True)

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
