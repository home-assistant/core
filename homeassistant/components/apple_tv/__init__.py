"""The Apple TV integration."""
import asyncio
import logging
from random import randrange

from pyatv import connect, exceptions, scan
from pyatv.const import DeviceModel, Protocol
from pyatv.convert import model_str

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CONNECTIONS,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SUGGESTED_AREA,
    ATTR_SW_VERSION,
    CONF_ADDRESS,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import CONF_CREDENTIALS, CONF_IDENTIFIERS, CONF_START_OFF, DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Apple TV"

BACKOFF_TIME_LOWER_LIMIT = 15  # seconds
BACKOFF_TIME_UPPER_LIMIT = 300  # Five minutes

SIGNAL_CONNECTED = "apple_tv_connected"
SIGNAL_DISCONNECTED = "apple_tv_disconnected"

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.REMOTE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry for Apple TV."""
    manager = AppleTVManager(hass, entry)

    if manager.is_on:
        await manager.connect_once(raise_missing_credentials=True)
        if not manager.atv:
            address = entry.data[CONF_ADDRESS]
            raise ConfigEntryNotReady(f"Not found at {address}, waiting for discovery")

    hass.data.setdefault(DOMAIN, {})[entry.unique_id] = manager

    async def on_hass_stop(event):
        """Stop push updates when hass stops."""
        await manager.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await manager.init()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Apple TV config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        manager = hass.data[DOMAIN].pop(entry.unique_id)
        await manager.disconnect()

    return unload_ok


class AppleTVEntity(Entity):
    """Device that sends commands to an Apple TV."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, name, identifier, manager):
        """Initialize device."""
        self.atv = None
        self.manager = manager
        self._attr_unique_id = identifier
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            name=name,
        )

    async def async_added_to_hass(self):
        """Handle when an entity is about to be added to Home Assistant."""

        @callback
        def _async_connected(atv):
            """Handle that a connection was made to a device."""
            self.atv = atv
            self.async_device_connected(atv)
            self.async_write_ha_state()

        @callback
        def _async_disconnected():
            """Handle that a connection to a device was lost."""
            self.async_device_disconnected()
            self.atv = None
            self.async_write_ha_state()

        if self.manager.atv:
            # ATV is already connected
            _async_connected(self.manager.atv)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{SIGNAL_CONNECTED}_{self.unique_id}", _async_connected
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_DISCONNECTED}_{self.unique_id}",
                _async_disconnected,
            )
        )

    def async_device_connected(self, atv):
        """Handle when connection is made to device."""

    def async_device_disconnected(self):
        """Handle when connection was lost to device."""


class AppleTVManager:
    """Connection and power manager for an Apple TV.

    An instance is used per device to share the same power state between
    several platforms. It also manages scanning and connection establishment
    in case of problems.
    """

    def __init__(self, hass, config_entry):
        """Initialize power manager."""
        self.config_entry = config_entry
        self.hass = hass
        self.atv = None
        self.is_on = not config_entry.options.get(CONF_START_OFF, False)
        self._connection_attempts = 0
        self._connection_was_lost = False
        self._task = None

    async def init(self):
        """Initialize power management."""
        if self.is_on:
            await self.connect()

    def connection_lost(self, _):
        """Device was unexpectedly disconnected.

        This is a callback function from pyatv.interface.DeviceListener.
        """
        _LOGGER.warning(
            'Connection lost to Apple TV "%s"', self.config_entry.data[CONF_NAME]
        )
        self._connection_was_lost = True
        self._handle_disconnect()

    def connection_closed(self):
        """Device connection was (intentionally) closed.

        This is a callback function from pyatv.interface.DeviceListener.
        """
        self._handle_disconnect()

    def _handle_disconnect(self):
        """Handle that the device disconnected and restart connect loop."""
        if self.atv:
            self.atv.close()
            self.atv = None
        self._dispatch_send(SIGNAL_DISCONNECTED)
        self._start_connect_loop()

    async def connect(self):
        """Connect to device."""
        self.is_on = True
        self._start_connect_loop()

    async def disconnect(self):
        """Disconnect from device."""
        _LOGGER.debug("Disconnecting from device")
        self.is_on = False
        try:
            if self.atv:
                self.atv.close()
                self.atv = None
            if self._task:
                self._task.cancel()
                self._task = None
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("An error occurred while disconnecting")

    def _start_connect_loop(self):
        """Start background connect loop to device."""
        if not self._task and self.atv is None and self.is_on:
            self._task = asyncio.create_task(self._connect_loop())
        else:
            _LOGGER.debug(
                "Not starting connect loop (%s, %s)", self.atv is None, self.is_on
            )

    async def connect_once(self, raise_missing_credentials):
        """Try to connect once."""
        try:
            if conf := await self._scan():
                await self._connect(conf, raise_missing_credentials)
        except exceptions.AuthenticationError:
            self.config_entry.async_start_reauth(self.hass)
            await self.disconnect()
            _LOGGER.exception(
                "Authentication failed for %s, try reconfiguring device",
                self.config_entry.data[CONF_NAME],
            )
            return
        except asyncio.CancelledError:
            pass
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Failed to connect")
            self.atv = None

    async def _connect_loop(self):
        """Connect loop background task function."""
        _LOGGER.debug("Starting connect loop")

        # Try to find device and connect as long as the user has said that
        # we are allowed to connect and we are not already connected.
        while self.is_on and self.atv is None:
            await self.connect_once(raise_missing_credentials=False)
            if self.atv is not None:
                break
            self._connection_attempts += 1
            backoff = min(
                max(
                    BACKOFF_TIME_LOWER_LIMIT,
                    randrange(2**self._connection_attempts),
                ),
                BACKOFF_TIME_UPPER_LIMIT,
            )

            _LOGGER.debug("Reconnecting in %d seconds", backoff)
            await asyncio.sleep(backoff)

        _LOGGER.debug("Connect loop ended")
        self._task = None

    async def _scan(self):
        """Try to find device by scanning for it."""
        identifiers = set(
            self.config_entry.data.get(CONF_IDENTIFIERS, [self.config_entry.unique_id])
        )
        address = self.config_entry.data[CONF_ADDRESS]

        # Only scan for and set up protocols that was successfully paired
        protocols = {
            Protocol(int(protocol))
            for protocol in self.config_entry.data[CONF_CREDENTIALS]
        }

        _LOGGER.debug("Discovering device %s", self.config_entry.title)
        aiozc = await zeroconf.async_get_async_instance(self.hass)
        atvs = await scan(
            self.hass.loop,
            identifier=identifiers,
            protocol=protocols,
            hosts=[address],
            aiozc=aiozc,
        )
        if atvs:
            return atvs[0]

        _LOGGER.debug(
            "Failed to find device %s with address %s",
            self.config_entry.title,
            address,
        )
        # We no longer multicast scan for the device since as soon as async_step_zeroconf runs,
        # it will update the address and reload the config entry when the device is found.
        return None

    async def _connect(self, conf, raise_missing_credentials):
        """Connect to device."""
        credentials = self.config_entry.data[CONF_CREDENTIALS]
        name = self.config_entry.data[CONF_NAME]
        missing_protocols = []
        for protocol_int, creds in credentials.items():
            protocol = Protocol(int(protocol_int))
            if conf.get_service(protocol) is not None:
                conf.set_credentials(protocol, creds)
            else:
                missing_protocols.append(protocol.name)

        if missing_protocols:
            missing_protocols_str = ", ".join(missing_protocols)
            if raise_missing_credentials:
                raise ConfigEntryNotReady(
                    f"Protocol(s) {missing_protocols_str} not yet found for {name},"
                    " waiting for discovery."
                )
            _LOGGER.info(
                "Protocol(s) %s not yet found for %s, trying later",
                missing_protocols_str,
                name,
            )
            return

        _LOGGER.debug("Connecting to device %s", self.config_entry.data[CONF_NAME])
        session = async_get_clientsession(self.hass)
        self.atv = await connect(conf, self.hass.loop, session=session)
        self.atv.listener = self

        self._dispatch_send(SIGNAL_CONNECTED, self.atv)
        self._address_updated(str(conf.address))

        self._async_setup_device_registry()

        self._connection_attempts = 0
        if self._connection_was_lost:
            _LOGGER.info(
                'Connection was re-established to device "%s"',
                self.config_entry.data[CONF_NAME],
            )
            self._connection_was_lost = False

    @callback
    def _async_setup_device_registry(self):
        attrs = {
            ATTR_IDENTIFIERS: {(DOMAIN, self.config_entry.unique_id)},
            ATTR_MANUFACTURER: "Apple",
            ATTR_NAME: self.config_entry.data[CONF_NAME],
        }
        attrs[ATTR_SUGGESTED_AREA] = attrs[ATTR_NAME].removesuffix(f" {DEFAULT_NAME}")

        if self.atv:
            dev_info = self.atv.device_info

            attrs[ATTR_MODEL] = (
                dev_info.raw_model
                if dev_info.model == DeviceModel.Unknown and dev_info.raw_model
                else model_str(dev_info.model)
            )
            attrs[ATTR_SW_VERSION] = dev_info.version

            if dev_info.mac:
                attrs[ATTR_CONNECTIONS] = {(dr.CONNECTION_NETWORK_MAC, dev_info.mac)}

        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id, **attrs
        )

    @property
    def is_connecting(self):
        """Return true if connection is in progress."""
        return self._task is not None

    def _address_updated(self, address):
        """Update cached address in config entry."""
        _LOGGER.debug("Changing address to %s", address)
        self.hass.config_entries.async_update_entry(
            self.config_entry, data={**self.config_entry.data, CONF_ADDRESS: address}
        )

    def _dispatch_send(self, signal, *args):
        """Dispatch a signal to all entities managed by this manager."""
        async_dispatcher_send(
            self.hass, f"{signal}_{self.config_entry.unique_id}", *args
        )
