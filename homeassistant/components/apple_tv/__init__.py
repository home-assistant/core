"""The Apple TV integration."""

from __future__ import annotations

import asyncio
import logging
from random import randrange
from typing import Any, cast

from pyatv import connect, exceptions, scan
from pyatv.conf import AppleTV
from pyatv.const import DeviceModel, Protocol
from pyatv.convert import model_str
from pyatv.interface import AppleTV as AppleTVInterface, DeviceListener

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
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_CREDENTIALS,
    CONF_IDENTIFIERS,
    CONF_START_OFF,
    DOMAIN,
    SIGNAL_CONNECTED,
    SIGNAL_DISCONNECTED,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME_TV = "Apple TV"
DEFAULT_NAME_HP = "HomePod"

BACKOFF_TIME_LOWER_LIMIT = 15  # seconds
BACKOFF_TIME_UPPER_LIMIT = 300  # Five minutes

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.REMOTE]

AUTH_EXCEPTIONS = (
    exceptions.AuthenticationError,
    exceptions.InvalidCredentialsError,
    exceptions.NoCredentialsError,
)
CONNECTION_TIMEOUT_EXCEPTIONS = (
    OSError,
    asyncio.CancelledError,
    TimeoutError,
    exceptions.ConnectionLostError,
    exceptions.ConnectionFailedError,
)
DEVICE_EXCEPTIONS = (
    exceptions.ProtocolError,
    exceptions.NoServiceError,
    exceptions.PairingError,
    exceptions.BackOffError,
    exceptions.DeviceIdMissingError,
)

type AppleTvConfigEntry = ConfigEntry[AppleTVManager]


async def async_setup_entry(hass: HomeAssistant, entry: AppleTvConfigEntry) -> bool:
    """Set up a config entry for Apple TV."""
    manager = AppleTVManager(hass, entry)

    if manager.is_on:
        address = entry.data[CONF_ADDRESS]

        try:
            await manager.async_first_connect()
        except AUTH_EXCEPTIONS as ex:
            raise ConfigEntryAuthFailed(
                f"{address}: Authentication failed, try reconfiguring device: {ex}"
            ) from ex
        except CONNECTION_TIMEOUT_EXCEPTIONS as ex:
            raise ConfigEntryNotReady(f"{address}: {ex}") from ex
        except DEVICE_EXCEPTIONS as ex:
            _LOGGER.debug(
                "Error setting up apple_tv at %s: %s", address, ex, exc_info=ex
            )
            raise ConfigEntryNotReady(f"{address}: {ex}") from ex

    entry.runtime_data = manager

    async def on_hass_stop(event: Event) -> None:
        """Stop push updates when hass stops."""
        await manager.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )
    entry.async_on_unload(manager.disconnect)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await manager.init()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Apple TV config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class AppleTVManager(DeviceListener):
    """Connection and power manager for an Apple TV.

    An instance is used per device to share the same power state between
    several platforms. It also manages scanning and connection establishment
    in case of problems.
    """

    atv: AppleTVInterface | None = None
    _connection_attempts = 0
    _connection_was_lost = False
    _task: asyncio.Task[None] | None = None

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize power manager."""
        self.config_entry = config_entry
        self.hass = hass
        self.is_on = not config_entry.options.get(CONF_START_OFF, False)

    async def init(self) -> None:
        """Initialize power management."""
        if self.is_on:
            await self.connect()

    def connection_lost(self, exception: Exception) -> None:
        """Device was unexpectedly disconnected.

        This is a callback function from pyatv.interface.DeviceListener.
        """
        _LOGGER.warning(
            'Connection lost to Apple TV "%s"', self.config_entry.data[CONF_NAME]
        )
        self._connection_was_lost = True
        self._handle_disconnect()

    def connection_closed(self) -> None:
        """Device connection was (intentionally) closed.

        This is a callback function from pyatv.interface.DeviceListener.
        """
        self._handle_disconnect()

    def _handle_disconnect(self) -> None:
        """Handle that the device disconnected and restart connect loop."""
        if self.atv:
            self.atv.close()
            self.atv = None
        self._dispatch_send(SIGNAL_DISCONNECTED)
        self._start_connect_loop()

    async def connect(self) -> None:
        """Connect to device."""
        self.is_on = True
        self._start_connect_loop()

    async def disconnect(self) -> None:
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
        except Exception:
            _LOGGER.exception("An error occurred while disconnecting")

    def _start_connect_loop(self) -> None:
        """Start background connect loop to device."""
        if not self._task and self.atv is None and self.is_on:
            self._task = self.config_entry.async_create_background_task(
                self.hass,
                self._connect_loop(),
                name=f"apple_tv connect loop {self.config_entry.title}",
                eager_start=True,
            )
        else:
            _LOGGER.debug(
                "Not starting connect loop (%s, %s)", self.atv is None, self.is_on
            )

    async def _connect_once(self, raise_missing_credentials: bool) -> None:
        """Connect to device once."""
        if conf := await self._scan():
            await self._connect(conf, raise_missing_credentials)

    async def async_first_connect(self) -> None:
        """Connect to device for the first time."""
        connect_ok = False
        try:
            await self._connect_once(raise_missing_credentials=True)
            connect_ok = True
        finally:
            if not connect_ok:
                await self.disconnect()

    async def connect_once(self, raise_missing_credentials: bool) -> None:
        """Try to connect once."""
        try:
            await self._connect_once(raise_missing_credentials)
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
        except Exception:
            _LOGGER.exception("Failed to connect")
            await self.disconnect()

    async def _connect_loop(self) -> None:
        """Connect loop background task function."""
        _LOGGER.debug("Starting connect loop")

        # Try to find device and connect as long as the user has said that
        # we are allowed to connect and we are not already connected.
        while self.is_on and self.atv is None:
            await self.connect_once(raise_missing_credentials=False)
            if self.atv is not None:
                # Calling self.connect_once may have set self.atv
                break  # type: ignore[unreachable]
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

    async def _scan(self) -> AppleTV | None:
        """Try to find device by scanning for it."""
        config_entry = self.config_entry
        identifiers: set[str] = set(
            config_entry.data.get(CONF_IDENTIFIERS, [config_entry.unique_id])
        )
        address: str = config_entry.data[CONF_ADDRESS]
        hass = self.hass

        # Only scan for and set up protocols that was successfully paired
        protocols = {
            Protocol(int(protocol)) for protocol in config_entry.data[CONF_CREDENTIALS]
        }

        _LOGGER.debug("Discovering device %s", config_entry.title)
        aiozc = await zeroconf.async_get_async_instance(hass)
        atvs = await scan(
            hass.loop,
            identifier=identifiers,
            protocol=protocols,
            hosts=[address],
            aiozc=aiozc,
        )
        if atvs:
            return cast(AppleTV, atvs[0])

        _LOGGER.debug(
            "Failed to find device %s with address %s",
            config_entry.title,
            address,
        )
        # We no longer multicast scan for the device since as soon as async_step_zeroconf runs,
        # it will update the address and reload the config entry when the device is found.
        return None

    async def _connect(self, conf: AppleTV, raise_missing_credentials: bool) -> None:
        """Connect to device."""
        config_entry = self.config_entry
        credentials: dict[int, str | None] = config_entry.data[CONF_CREDENTIALS]
        name: str = config_entry.data[CONF_NAME]
        missing_protocols = []
        for protocol_int, creds in credentials.items():
            protocol = Protocol(int(protocol_int))
            if conf.get_service(protocol) is not None:
                conf.set_credentials(protocol, creds)  # type: ignore[arg-type]
            else:
                missing_protocols.append(protocol.name)

        if missing_protocols:
            missing_protocols_str = ", ".join(missing_protocols)
            if raise_missing_credentials:
                raise ConfigEntryNotReady(
                    f"Protocol(s) {missing_protocols_str} not yet found for {name},"
                    " waiting for discovery."
                )
            _LOGGER.debug(
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
            _LOGGER.warning(
                'Connection was re-established to device "%s"',
                self.config_entry.data[CONF_NAME],
            )
            self._connection_was_lost = False

    @callback
    def _async_setup_device_registry(self) -> None:
        attrs = {
            ATTR_IDENTIFIERS: {(DOMAIN, self.config_entry.unique_id)},
            ATTR_MANUFACTURER: "Apple",
            ATTR_NAME: self.config_entry.data[CONF_NAME],
        }
        attrs[ATTR_SUGGESTED_AREA] = (
            attrs[ATTR_NAME]
            .removesuffix(f" {DEFAULT_NAME_TV}")
            .removesuffix(f" {DEFAULT_NAME_HP}")
        )

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
    def is_connecting(self) -> bool:
        """Return true if connection is in progress."""
        return self._task is not None

    def _address_updated(self, address: str) -> None:
        """Update cached address in config entry."""
        _LOGGER.debug("Changing address to %s", address)
        self.hass.config_entries.async_update_entry(
            self.config_entry, data={**self.config_entry.data, CONF_ADDRESS: address}
        )

    def _dispatch_send(self, signal: str, *args: Any) -> None:
        """Dispatch a signal to all entities managed by this manager."""
        async_dispatcher_send(
            self.hass, f"{signal}_{self.config_entry.unique_id}", *args
        )
