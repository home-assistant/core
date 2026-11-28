"""Representation of a Haus-Bus gateway."""

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING
from weakref import WeakKeyDictionary

from pyhausbus.ABusFeature import ABusFeature
from pyhausbus.BusDataMessage import BusDataMessage
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.Configuration import (
    Configuration,
)
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.ModuleId import ModuleId
from pyhausbus.HomeServer import HomeServer
from pyhausbus.IBusDataListener import IBusDataListener
from pyhausbus.IBusDeviceListener import IBusDeviceListener
from pyhausbus.ObjectId import ObjectId

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, NEW_CHANNEL_ADDED

if TYPE_CHECKING:
    from . import HausbusConfigEntry

LOGGER = logging.getLogger(__name__)

# Serializes HomeServer reference-count updates and shutdown.
_home_server_lock = asyncio.Lock()

# HomeServer is a process-wide singleton shared by config flows and the config
# entry, so references are counted here instead of in runtime_data.
_home_server_refs: WeakKeyDictionary[HomeServer, int] = WeakKeyDictionary()


class _HomeServerBrokenState:
    """Whether the shared HomeServer is unusable until Home Assistant restarts.

    Not tracked per instance: pyhausbus clears its singleton before shutdown()
    raises, so the next HomeServer() returns a new object a per-instance marker
    would never match.
    """

    broken = False


_home_server_broken_state = _HomeServerBrokenState()


class HomeServerUnavailable(HomeAssistantError):
    """The shared HomeServer failed to shut down and cannot be reopened."""


async def async_acquire_home_server(hass: HomeAssistant) -> HomeServer:
    """Acquire a reference to the shared HomeServer, creating it on first use.

    Raises HomeServerUnavailable after a failed shutdown, until Home Assistant
    restarts. Pair every call with async_release_home_server().
    """
    async with _home_server_lock:
        if _home_server_broken_state.broken:
            raise HomeServerUnavailable(
                "The Haus-Bus network connection failed to shut down "
                "cleanly earlier and cannot be reopened until Home "
                "Assistant restarts"
            )

        home_server_job = hass.async_add_executor_job(HomeServer)
        try:
            home_server = await asyncio.shield(home_server_job)
        except asyncio.CancelledError:
            with contextlib.suppress(Exception):
                await home_server_job

            _release_cancelled_home_server(hass, home_server_job)
            raise

        _home_server_refs[home_server] = _home_server_refs.get(home_server, 0) + 1
        return home_server


def _release_cancelled_home_server(
    hass: HomeAssistant, home_server_job: asyncio.Future[HomeServer]
) -> None:
    """Shut down the HomeServer of a cancelled acquisition once it is built.

    Never decrements the refcount, since this acquisition never incremented it.
    """
    if home_server_job.cancelled():
        return
    try:
        home_server = home_server_job.result()
    except Exception:
        LOGGER.debug(
            "HomeServer construction failed after its acquisition was cancelled",
            exc_info=True,
        )
        return
    hass.async_create_task(_async_shutdown_unreferenced_home_server(hass, home_server))


async def _async_shutdown_unreferenced_home_server(
    hass: HomeAssistant, home_server: HomeServer
) -> None:
    """Shut down a HomeServer, unless something has acquired it since."""
    async with _home_server_lock:
        if _home_server_refs.get(home_server, 0) > 0:
            return
        try:
            shutdown_job = hass.async_add_executor_job(home_server.shutdown)
            await asyncio.shield(shutdown_job)
        except asyncio.CancelledError:
            with contextlib.suppress(Exception):
                await shutdown_job
            if shutdown_job.done() and shutdown_job.exception() is not None:
                _home_server_broken_state.broken = True
            raise
        except Exception:
            _home_server_broken_state.broken = True
            raise


async def async_release_home_server(
    hass: HomeAssistant, home_server: HomeServer
) -> None:
    """Release a HomeServer reference, shutting it down once unused.

    A RuntimeError from shutdown() means a pyhausbus thread is still alive. It
    propagates and marks the HomeServer unavailable until Home Assistant
    restarts. The shutdown job is shielded so the lock is not released while
    it is still running.
    """
    async with _home_server_lock:
        refcount = _home_server_refs.get(home_server, 0) - 1
        if refcount <= 0:
            _home_server_refs.pop(home_server, None)
            try:
                shutdown_job = hass.async_add_executor_job(home_server.shutdown)
                await asyncio.shield(shutdown_job)
            except asyncio.CancelledError:
                with contextlib.suppress(Exception):
                    await shutdown_job
                if shutdown_job.done() and shutdown_job.exception() is not None:
                    _home_server_broken_state.broken = True
                raise
            except Exception:
                _home_server_broken_state.broken = True
                raise
        else:
            _home_server_refs[home_server] = refcount


class HausbusGateway(IBusDataListener, IBusDeviceListener):
    """Manages a Haus-Bus gateway."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HausbusConfigEntry,
        home_server: HomeServer,
    ) -> None:
        """Initialize the system."""
        self.hass = hass
        self.config_entry = config_entry
        self.home_server = home_server
        self.home_server.addBusEventListener(self)
        self.home_server.addBusDeviceListener(self)

        # Prevents duplicate channels from being dispatched more than once.
        self.registered_channels: set[int] = set()
        self.discovery_task: asyncio.Task[None] | None = None

        # Channels found before platform setup finishes are buffered here.
        self._platform_ready: bool = False
        self._pending_channels: list[tuple[ABusFeature, DeviceInfo]] = []

    @classmethod
    async def async_create(
        cls, hass: HomeAssistant, config_entry: HausbusConfigEntry
    ) -> HausbusGateway:
        """Create the gateway, opening the Haus-Bus network connection."""
        home_server = await async_acquire_home_server(hass)
        return cls(hass, config_entry, home_server)

    async def start_discovery(self) -> None:
        """Start device discovery."""
        LOGGER.debug("Search devices")
        await self.hass.async_add_executor_job(self.home_server.searchDevices)

    def newDeviceDetected(
        self,
        device_id: int,
        model_type: str | None,
        module_id: ModuleId,
        configuration: Configuration,
        channels: list[ABusFeature],
    ) -> None:
        """Handle new discovered Haus-Bus device."""
        LOGGER.debug(
            "newDeviceDetected: device_id %s model_type %s module_id %s configuration %s",
            device_id,
            model_type,
            module_id,
            configuration,
        )

        device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            manufacturer="HausBus",
            model=model_type,
            name=f"{model_type or 'Haus-Bus device'} {device_id}",
            sw_version=module_id.getFirmwareId().getTemplateId()
            + " "
            + str(module_id.getMajorRelease())
            + " "
            + str(module_id.getMinorRelease()),
            # name of moduleId reports hw version with leading $MOD$
            hw_version=module_id.getName().removeprefix("$MOD$ "),
        )

        for channel in channels:
            self.hass.loop.call_soon_threadsafe(
                self._register_channel, channel, device_info
            )

    def _register_channel(self, channel: ABusFeature, device_info: DeviceInfo) -> None:
        """Register a discovered channel on the event loop.

        newDeviceDetected() runs on a pyhausbus thread and must not touch the
        registration state directly.
        """
        object_id = channel.getObjectId()
        if object_id in self.registered_channels:
            return
        self.registered_channels.add(object_id)
        if self._platform_ready:
            async_dispatcher_send(self.hass, NEW_CHANNEL_ADDED, channel, device_info)
        else:
            self._pending_channels.append((channel, device_info))

    def pause_channel_dispatch(self) -> None:
        """Buffer newly discovered channels while the platform is unloading."""
        self._platform_ready = False

    async def async_flush_pending_channels(self) -> None:
        """Mark the platform ready and dispatch the buffered channels.

        Also undoes pause_channel_dispatch() when an unload fails.
        """
        self._platform_ready = True
        for channel, device_info in self._pending_channels:
            async_dispatcher_send(self.hass, NEW_CHANNEL_ADDED, channel, device_info)
        self._pending_channels.clear()

    def busDataReceived(self, busDataMessage: BusDataMessage) -> None:
        """Handle Haus-Bus messages."""
        object_id = ObjectId(busDataMessage.getSenderObjectId())
        device_id = object_id.getDeviceId()
        data = busDataMessage.getData()

        # ignore messages from own server
        if self.home_server.is_internal_device(device_id):
            return

        LOGGER.debug("busDataReceived: data %s from %s", data, object_id)

        self.hass.loop.call_soon_threadsafe(
            async_dispatcher_send,
            self.hass,
            f"hausbus_update_{object_id.getValue()}",
            data,
        )
