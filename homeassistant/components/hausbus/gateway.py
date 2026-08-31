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
from pyhausbus.ObjectId import ObjectId

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, NEW_CHANNEL_ADDED

if TYPE_CHECKING:
    from . import HausbusConfigEntry

LOGGER = logging.getLogger(__name__)

# Serialize process-wide HomeServer reference-count updates.
_home_server_lock = asyncio.Lock()

# HomeServer is a process-wide singleton (see pyhausbus.HomeServer), not
# something scoped to a single hass instance, and it must be reachable
# from a config flow before any config entry - and its runtime_data -
# exists. So its reference count is tracked here, keyed on the HomeServer
# instance itself, rather than in hass.data. Using a WeakKeyDictionary
# also means this needs no manual reset between tests: a mocked HomeServer
# is a fresh object per test and simply starts out with no entry.
_home_server_refs: WeakKeyDictionary[HomeServer, int] = WeakKeyDictionary()

# HomeServer instances whose shutdown() failed to fully stop their worker
# or collector thread (see async_release_home_server). pyhausbus.HomeServer()
# keeps returning this very same object until shutdown() completes without
# error, so without this, a fresh async_acquire_home_server() call - from a
# config flow, or a later setup attempt - could hand this half torn-down
# instance straight back out.
_broken_home_servers: WeakKeyDictionary[HomeServer, None] = WeakKeyDictionary()


async def async_acquire_home_server(hass: HomeAssistant) -> HomeServer:
    """Acquire a reference to the shared HomeServer, creating it on first use.

    Every HomeServer() call in this process returns the very same object
    until shutdown() is called. In-progress config flows (discovering
    devices) and the active config entry's gateway can all hold a
    reference to it at the same time, so teardown has to be reference
    counted here rather than triggered by whichever caller happens to
    finish first - otherwise one flow being aborted could tear down the
    HomeServer that another flow, or the config entry, is still using.

    Raises OSError if a previous release left this singleton unable to
    fully shut down (see async_release_home_server) - it cannot be handed
    out again until Home Assistant restarts and starts a fresh process.

    Always pair a call to this with async_release_home_server(), passing
    back the exact object this returned.
    """
    async with _home_server_lock:
        home_server_job = hass.async_add_executor_job(HomeServer)
        try:
            home_server = await asyncio.shield(home_server_job)
        except asyncio.CancelledError:
            with contextlib.suppress(Exception):
                await home_server_job

            _release_cancelled_home_server(hass, home_server_job)
            raise

        if home_server in _broken_home_servers:
            raise OSError(
                "The Haus-Bus network connection failed to shut down "
                "cleanly earlier and cannot be reopened until Home "
                "Assistant restarts"
            )

        _home_server_refs[home_server] = _home_server_refs.get(home_server, 0) + 1
        return home_server


def _release_cancelled_home_server(
    hass: HomeAssistant, home_server_job: asyncio.Future[HomeServer]
) -> None:
    """Release a HomeServer whose acquirer was cancelled before it finished.

    Called once the executor job backing a cancelled async_acquire_home_server()
    call completes. Schedules a cleanup that shuts the HomeServer back down,
    but only if it is still unreferenced - it must not simply decrement the
    refcount via async_release_home_server(), since that was never
    incremented for this cancelled acquisition and doing so could tear down
    a singleton another flow or the active gateway still owns.
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
    """Shut down a HomeServer, but only if nothing has since acquired it.

    Unlike async_release_home_server(), this never decrements
    _home_server_refs: the HomeServer this is called for was never
    registered there in the first place (its acquisition was cancelled), so
    treating this as a normal release would incorrectly tear down a
    singleton another flow or the active gateway has since started using.
    """
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
                _broken_home_servers[home_server] = None
            raise
        except Exception:
            _broken_home_servers[home_server] = None
            raise


async def async_release_home_server(
    hass: HomeAssistant, home_server: HomeServer
) -> None:
    """Release a HomeServer reference, shutting it down once no longer used.

    pyhausbus's shutdown() raises RuntimeError if its background worker or
    collector thread is still alive after their join timeout. That is a
    real failure to fully release the HomeServer's resources - swallowing
    it here would report a successful unload while a stray thread could
    still be running against a HomeServer a subsequent reload replaces, so
    it is intentionally left to propagate rather than caught. The failed
    HomeServer is instead marked (see _broken_home_servers) so a later
    async_acquire_home_server() call refuses to hand this same half
    torn-down instance back out.

    The shutdown executor job itself is shielded from cancellation: this
    coroutine may be cancelled (e.g. during Home Assistant shutdown) while
    shutdown() is still running on its worker thread. Since that thread
    keeps running regardless, releasing _home_server_lock before it
    actually finishes would let a concurrent acquirer receive the same
    still-shutting-down singleton.
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
                    _broken_home_servers[home_server] = None
                raise
            except Exception:
                _broken_home_servers[home_server] = None
                raise
        else:
            _home_server_refs[home_server] = refcount


class HausbusGateway(IBusDataListener):
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

        # Channels discovered before the cover platform has finished setup
        # cannot be consumed by its NEW_CHANNEL_ADDED listener yet. They are
        # buffered here and flushed by async_flush_pending_channels() once
        # async_forward_entry_setups() returns.
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
        """Register a single discovered channel.

        Runs on the Home Assistant event loop, the same thread as
        async_flush_pending_channels(), so checking/updating
        registered_channels, _platform_ready and _pending_channels here
        cannot race with it: newDeviceDetected() is called from pyhausbus's
        DeviceWorker thread and must not touch this state directly.
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
        """Mark the platform ready and dispatch channels buffered while not.

        Called once async_forward_entry_setups() has returned, so that any
        channels discovered during platform setup are delivered to the
        now-registered NEW_CHANNEL_ADDED listeners. Also undoes
        pause_channel_dispatch() if the unload it was guarding fails, so
        the gateway keeps discovering devices normally for as long as it
        keeps running.
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
