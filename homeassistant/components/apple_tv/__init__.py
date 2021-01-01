"""The Apple TV integration."""
import asyncio
import logging
from random import randrange

from pyatv import connect, exceptions, scan
from pyatv.const import Protocol

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_NAME,
    CONF_PROTOCOL,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity

from .const import CONF_CREDENTIALS, CONF_IDENTIFIER, CONF_START_OFF, DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Apple TV"

BACKOFF_TIME_UPPER_LIMIT = 300  # Five minutes

NOTIFICATION_TITLE = "Apple TV Notification"
NOTIFICATION_ID = "apple_tv_notification"

SOURCE_REAUTH = "reauth"

SIGNAL_CONNECTED = "apple_tv_connected"
SIGNAL_DISCONNECTED = "apple_tv_disconnected"

PLATFORMS = [MP_DOMAIN, REMOTE_DOMAIN]


async def async_setup(hass, config):
    """Set up the Apple TV integration."""
    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry for Apple TV."""
    manager = AppleTVManager(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.unique_id] = manager

    async def on_hass_stop(event):
        """Stop push updates when hass stops."""
        await manager.disconnect()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)

    async def setup_platforms():
        """Set up platforms and initiate connection."""
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_setup(entry, component)
                for component in PLATFORMS
            ]
        )
        await manager.init()

    hass.async_create_task(setup_platforms())

    return True


async def async_unload_entry(hass, entry):
    """Unload an Apple TV config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        manager = hass.data[DOMAIN].pop(entry.unique_id)
        await manager.disconnect()

    return unload_ok


class AppleTVEntity(Entity):
    """Device that sends commands to an Apple TV."""

    def __init__(self, name, identifier, manager):
        """Initialize device."""
        self.atv = None
        self.manager = manager
        self._name = name
        self._identifier = identifier

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

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{SIGNAL_CONNECTED}_{self._identifier}", _async_connected
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_DISCONNECTED}_{self._identifier}",
                _async_disconnected,
            )
        )

    def async_device_connected(self, atv):
        """Handle when connection is made to device."""

    def async_device_disconnected(self):
        """Handle when connection was lost to device."""

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._identifier

    @property
    def should_poll(self):
        """No polling needed for Apple TV."""
        return False


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
        self._is_on = not config_entry.options.get(CONF_START_OFF, False)
        self._connection_attempts = 0
        self._connection_was_lost = False
        self._task = None

    async def init(self):
        """Initialize power management."""
        if self._is_on:
            await self.connect()

    def connection_lost(self, _):
        """Device was unexpectedly disconnected.

        This is a callback function from pyatv.interface.DeviceListener.
        """
        _LOGGER.warning('Connection lost to Apple TV "%s"', self.atv.name)
        if self.atv:
            self.atv.close()
            self.atv = None
        self._connection_was_lost = True
        self._dispatch_send(SIGNAL_DISCONNECTED)
        self._start_connect_loop()

    def connection_closed(self):
        """Device connection was (intentionally) closed.

        This is a callback function from pyatv.interface.DeviceListener.
        """
        if self.atv:
            self.atv.close()
            self.atv = None
        self._dispatch_send(SIGNAL_DISCONNECTED)
        self._start_connect_loop()

    async def connect(self):
        """Connect to device."""
        self._is_on = True
        self._start_connect_loop()

    async def disconnect(self):
        """Disconnect from device."""
        _LOGGER.debug("Disconnecting from device")
        self._is_on = False
        try:
            if self.atv:
                self.atv.push_updater.listener = None
                self.atv.push_updater.stop()
                self.atv.close()
                self.atv = None
            if self._task:
                self._task.cancel()
                self._task = None
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("An error occurred while disconnecting")

    def _start_connect_loop(self):
        """Start background connect loop to device."""
        if not self._task and self.atv is None and self._is_on:
            self._task = asyncio.create_task(self._connect_loop())
        else:
            _LOGGER.debug(
                "Not starting connect loop (%s, %s)", self.atv is None, self._is_on
            )

    async def _connect_loop(self):
        """Connect loop background task function."""
        _LOGGER.debug("Starting connect loop")

        # Try to find device and connect as long as the user has said that
        # we are allowed to connect and we are not already connected.
        while self._is_on and self.atv is None:
            try:
                conf = await self._scan()
                if conf:
                    await self._connect(conf)
            except exceptions.AuthenticationError:
                self._auth_problem()
                break
            except asyncio.CancelledError:
                pass
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Failed to connect")
                self.atv = None

            if self.atv is None:
                self._connection_attempts += 1
                backoff = min(
                    randrange(2 ** self._connection_attempts), BACKOFF_TIME_UPPER_LIMIT
                )

                _LOGGER.debug("Reconnecting in %d seconds", backoff)
                await asyncio.sleep(backoff)

        _LOGGER.debug("Connect loop ended")
        self._task = None

    def _auth_problem(self):
        """Problem to authenticate occurred that needs intervention."""
        _LOGGER.debug("Authentication error, reconfigure integration")

        name = self.config_entry.data.get(CONF_NAME)
        identifier = self.config_entry.unique_id

        self.hass.components.persistent_notification.create(
            "An irrecoverable connection problem occurred when connecting to "
            f"`f{name}`. Please go to the Integrations page and reconfigure it",
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )

        # Add to event queue as this function is called from a task being
        # cancelled from disconnect
        asyncio.create_task(self.disconnect())

        self.hass.async_create_task(
            self.hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_REAUTH},
                data={CONF_NAME: name, CONF_IDENTIFIER: identifier},
            )
        )

    async def _scan(self):
        """Try to find device by scanning for it."""
        identifier = self.config_entry.unique_id
        address = self.config_entry.data[CONF_ADDRESS]
        protocol = Protocol(self.config_entry.data[CONF_PROTOCOL])

        _LOGGER.debug("Discovering device %s", identifier)
        atvs = await scan(
            self.hass.loop, identifier=identifier, protocol=protocol, hosts=[address]
        )
        if atvs:
            return atvs[0]

        _LOGGER.debug(
            "Failed to find device %s with address %s, trying to scan",
            identifier,
            address,
        )

        atvs = await scan(self.hass.loop, identifier=identifier, protocol=protocol)
        if atvs:
            return atvs[0]

        _LOGGER.debug("Failed to find device %s, trying later", identifier)

        return None

    async def _connect(self, conf):
        """Connect to device."""
        credentials = self.config_entry.data[CONF_CREDENTIALS]
        session = async_get_clientsession(self.hass)

        for protocol, creds in credentials.items():
            conf.set_credentials(Protocol(int(protocol)), creds)

        _LOGGER.debug("Connecting to device %s", self.config_entry.data[CONF_NAME])
        self.atv = await connect(conf, self.hass.loop, session=session)
        self.atv.listener = self

        self._dispatch_send(SIGNAL_CONNECTED, self.atv)
        self._address_updated(str(conf.address))

        await self._async_setup_device_registry()

        self._connection_attempts = 0
        if self._connection_was_lost:
            _LOGGER.info(
                'Connection was re-established to Apple TV "%s"', self.atv.service.name
            )
            self._connection_was_lost = False

    async def _async_setup_device_registry(self):
        attrs = {
            "identifiers": {(DOMAIN, self.config_entry.unique_id)},
            "manufacturer": "Apple",
            "name": self.config_entry.data[CONF_NAME],
        }

        if self.atv:
            dev_info = self.atv.device_info

            attrs["model"] = "Apple TV " + dev_info.model.name.replace("Gen", "")
            attrs["sw_version"] = dev_info.version

            if dev_info.mac:
                attrs["connections"] = {(dr.CONNECTION_NETWORK_MAC, dev_info.mac)}

        device_registry = await dr.async_get_registry(self.hass)
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
