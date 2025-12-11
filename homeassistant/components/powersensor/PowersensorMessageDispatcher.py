"""PowersensorMessageDispatcher is the main coordinator of messages.

The classes and utilities here mediate Powersensor PlugApi messages and updates/creation of Homeassistant Entities.
"""

import asyncio
from contextlib import suppress
import datetime
import logging
from typing import Any

from powersensor_local import PlugApi, VirtualHousehold

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .AsyncSet import AsyncSet
from .const import (
    # Used config entry fields
    CFG_ROLES,
    # Used signals
    CREATE_PLUG_SIGNAL,
    CREATE_SENSOR_SIGNAL,
    DATA_UPDATE_SIGNAL_FMT_MAC_EVENT,
    PLUG_ADDED_TO_HA_SIGNAL,
    ROLE_UPDATE_SIGNAL,
    SENSOR_ADDED_TO_HA_SIGNAL,
    ZEROCONF_ADD_PLUG_SIGNAL,
    ZEROCONF_REMOVE_PLUG_SIGNAL,
    ZEROCONF_UPDATE_PLUG_SIGNAL,
)

_LOGGER = logging.getLogger(__name__)


async def handle_exception(event: str, exc: BaseException):
    """Log errors when PlugApi throws an exception."""
    _LOGGER.error("On event %s Plug connection reported exception: %s", event, exc)


class PowersensorMessageDispatcher:
    """Message Dispatcher which sends and receives signals around HA entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        vhh: VirtualHousehold,
        debounce_timeout: float = 60,
    ) -> None:
        """Constructor for message dispatcher.

        This class mediates the push messages from the plug api and controls updates for HA entities.
        """
        self._hass = hass
        self._entry = entry
        self._vhh = vhh
        self.plugs: dict[str, PlugApi] = {}
        self._known_plugs: set[str] = set()
        self._known_plug_names: dict[str, str] = {}
        self.sensors: dict[str, str] = {}
        self.on_start_sensor_queue: dict[str, Any] = {}
        self._pending_removals: dict[str, asyncio.Task] = {}
        self._debounce_seconds = debounce_timeout
        self.has_solar = False
        self._solar_request_limit = datetime.timedelta(seconds=10)
        self._unsubscribe_from_signals = [
            async_dispatcher_connect(
                self._hass, ZEROCONF_ADD_PLUG_SIGNAL, self._plug_added
            ),
            async_dispatcher_connect(
                self._hass, ZEROCONF_UPDATE_PLUG_SIGNAL, self._plug_updated
            ),
            async_dispatcher_connect(
                self._hass, ZEROCONF_REMOVE_PLUG_SIGNAL, self._schedule_plug_removal
            ),
            async_dispatcher_connect(
                self._hass,
                PLUG_ADDED_TO_HA_SIGNAL,
                self._acknowledge_plug_added_to_homeassistant,
            ),
            async_dispatcher_connect(
                self._hass,
                SENSOR_ADDED_TO_HA_SIGNAL,
                self._acknowledge_sensor_added_to_homeassistant,
            ),
        ]

        self._monitor_add_plug_queue = None
        self._stop_task = False
        self._plug_added_queue: AsyncSet = AsyncSet()
        self._safe_to_process_plug_queue = False

    async def enqueue_plug_for_adding(self, network_info: dict):
        """On receiving zeroconf data this info is added to processing buffer to await creation of entity and api."""
        _LOGGER.debug("Adding to plug processing queue: %s", network_info)
        await self._plug_added_queue.add(
            (
                network_info["mac"],
                network_info["host"],
                network_info["port"],
                network_info["name"],
            )
        )

    async def process_plug_queue(self):
        """Start the background task if not already running."""
        self._safe_to_process_plug_queue = True
        if self._monitor_add_plug_queue is None or self._monitor_add_plug_queue.done():
            self._stop_task = False
            self._monitor_add_plug_queue = self._hass.async_create_background_task(
                self._monitor_plug_queue(), name="plug_queue_monitor"
            )
            _LOGGER.debug("Background task started")

    def _plug_has_been_seen(self, mac_address, name) -> bool:
        return (
            mac_address in self.plugs
            or mac_address in self._known_plugs
            or name in self._known_plug_names
        )

    async def _monitor_plug_queue(self):
        """The actual background task loop."""
        try:
            while not self._stop_task and self._plug_added_queue:
                queue_snapshot = await self._plug_added_queue.copy()
                for mac_address, host, port, name in queue_snapshot:
                    # @todo: maybe better to query the entity registry?
                    if not self._plug_has_been_seen(mac_address, name):
                        async_dispatcher_send(
                            self._hass,
                            CREATE_PLUG_SIGNAL,
                            mac_address,
                            host,
                            port,
                            name,
                        )
                    elif (
                        mac_address in self._known_plugs
                        and mac_address not in self.plugs
                    ):
                        _LOGGER.info(
                            "Plug with mac %s is known, but API is missing."
                            "Reconnecting without requesting entity creation... ",
                            mac_address,
                        )
                        self._create_api(mac_address, host, port, name)
                    else:
                        _LOGGER.debug(
                            "Plug: %s has already been created as an entity in Home Assistant."
                            " Skipping and flushing from queue. ",
                            mac_address,
                        )
                        await self._plug_added_queue.remove(
                            (mac_address, host, port, name)
                        )

                await asyncio.sleep(5)
            _LOGGER.debug("Plug queue has been processed!")

        except asyncio.CancelledError:
            _LOGGER.debug("Plug queue processing cancelled")
            raise
        except (
            TimeoutError,
            OSError,
            NotImplementedError,
        ) as e:  # just trying to add a little crash free safety, if not catch all errors
            _LOGGER.error("Error in Plug queue processing task: %s", e)
        finally:
            self._monitor_add_plug_queue = None

    async def stop_processing_plug_queue(self):
        """Stop the background task."""
        self._stop_task = True
        if self._monitor_add_plug_queue and not self._monitor_add_plug_queue.done():
            self._monitor_add_plug_queue.cancel()
            with suppress(asyncio.CancelledError):
                await self._monitor_add_plug_queue
            _LOGGER.debug("Background task stopped")
            self._monitor_add_plug_queue = None

    async def stop_pending_removal_tasks(self):
        """Stop the background removal tasks."""
        # create a temporary copy to avoid concurrency problems
        task_list = list(self._pending_removals.values())
        for task in task_list:
            if task and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

                _LOGGER.debug("Background removal task stopped")
        self._pending_removals = {}

    def _create_api(self, mac_address, ip, port, name):
        _LOGGER.info("Creating API for mac=%s, ip=%s, port=%s", mac_address, ip, port)
        api = PlugApi(mac=mac_address, ip=ip, port=port)
        self.plugs[mac_address] = api
        self._known_plugs.add(mac_address)
        self._known_plug_names[name] = mac_address
        known_evs = [
            "average_flow",
            "average_power",
            "average_power_components",
            "battery_level",
            "radio_signal_quality",
            "summation_energy",
            "summation_volume",
            #'uncalibrated_instant_reading',
        ]

        for ev in known_evs:
            api.subscribe(ev, self.handle_message)
        api.subscribe("now_relaying_for", self.handle_relaying_for)
        api.subscribe("exception", handle_exception)
        api.connect()

    async def cancel_any_pending_removal(self, mac, source):
        """Cancel removal of a plug that has been scheduled."""
        task = self._pending_removals.pop(mac, None)
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            _LOGGER.debug("Cancelled pending removal for %s by %s. ", mac, source)

    async def handle_relaying_for(self, event: str, message: dict):
        """Handle a potentially new sensor being reported."""
        mac = message.get("mac")
        device_type = message.get("device_type")
        if mac is None or device_type != "sensor":
            _LOGGER.warning(
                'Ignoring relayed device with MAC "%s" and type %s', mac, device_type
            )
            return

        persisted_role = self._entry.data.get(CFG_ROLES, {}).get(mac, None)
        role = message.get("role")
        _LOGGER.debug("Relayed sensor %s with role %s found", mac, role)

        if mac not in self.sensors:
            _LOGGER.debug("Reporting new sensor %s with role %s", mac, role)
            self.on_start_sensor_queue[mac] = role
            async_dispatcher_send(self._hass, CREATE_SENSOR_SIGNAL, mac, role)
        if role != persisted_role:
            _LOGGER.debug(
                "Restoring role for %s from %s to %s", mac, role, persisted_role
            )
            async_dispatcher_send(self._hass, ROLE_UPDATE_SIGNAL, mac, persisted_role)

    async def handle_message(self, event: str, message: dict):
        """Callback for handling messages from PlugApi.

        This includes but is not limited to: updating sensor data, device roles, canceling removal if data is still
        flowing from a device but zeroconf scheduled removal and signaling for creation of new Homeassistant entities.
        """
        mac = message["mac"]
        persisted_role = self._entry.data.get(CFG_ROLES, {}).get(mac, None)
        role = message.get("role", persisted_role)
        message["role"] = role

        if role != persisted_role:
            async_dispatcher_send(self._hass, ROLE_UPDATE_SIGNAL, mac, role)

        await self.cancel_any_pending_removal(mac, "new message received from plug")

        # Feed the household calculations
        if event == "average_power":
            await self._vhh.process_average_power_event(message)
        elif event == "summation_energy":
            await self._vhh.process_summation_event(message)

        async_dispatcher_send(
            self._hass, DATA_UPDATE_SIGNAL_FMT_MAC_EVENT % (mac, event), event, message
        )

        # Synthesise a role type message for the role diagnostic entity
        async_dispatcher_send(
            self._hass,
            DATA_UPDATE_SIGNAL_FMT_MAC_EVENT % (mac, "role"),
            "role",
            {"role": role},
        )

    async def disconnect(self):
        """Handle graceful disconnection of PlugApi objects."""
        for _ in range(len(self.plugs)):
            _, api = self.plugs.popitem()
            await api.disconnect()
        for unsubscribe in self._unsubscribe_from_signals:
            if unsubscribe is not None:
                unsubscribe()

        await self.stop_processing_plug_queue()
        await self.stop_pending_removal_tasks()

    @callback
    def _acknowledge_sensor_added_to_homeassistant(self, mac, role):
        self.sensors[mac] = role

    async def _acknowledge_plug_added_to_homeassistant(
        self, mac_address, host, port, name
    ):
        self._create_api(mac_address, host, port, name)
        await self._plug_added_queue.remove((mac_address, host, port, name))

    async def _plug_added(self, info):
        _LOGGER.debug(" Request to add plug received: %s", info)
        network_info = {}
        mac = info["properties"][b"id"].decode("utf-8")
        network_info["mac"] = mac
        await self.cancel_any_pending_removal(mac, "request to add plug")
        network_info["host"] = info["addresses"][0]
        network_info["port"] = info["port"]
        network_info["name"] = info["name"]

        if self._safe_to_process_plug_queue:
            await self.enqueue_plug_for_adding(network_info)
            await self.process_plug_queue()
        else:
            await self.enqueue_plug_for_adding(network_info)

    async def _plug_updated(self, info):
        _LOGGER.debug("Request to update plug received: %s", info)
        mac = info["properties"][b"id"].decode("utf-8")
        await self.cancel_any_pending_removal(mac, "request to update plug")
        host = info["addresses"][0]
        port = info["port"]
        name = info["name"]

        if mac in self.plugs:
            current_api: PlugApi = self.plugs[mac]
            if current_api.ip_address == host and current_api.port == port:
                _LOGGER.debug(
                    "Request to update plug with mac %s does not alter ip from existing API."
                    "IP still %s and port is %s. Skipping update... ",
                    mac,
                    host,
                    port,
                )
                return
            await current_api.disconnect()

        if mac in self._known_plugs:
            self._create_api(mac, host, port, name)
        else:
            network_info = {"mac": mac, "host": host, "port": port, "name": name}
            await self.enqueue_plug_for_adding(network_info)
            await self.process_plug_queue()

    async def _schedule_plug_removal(self, name, info):
        _LOGGER.debug("Request to delete plug received: %s", info)
        if name in self._known_plug_names:
            mac = self._known_plug_names[name]
            if mac in self.plugs:
                if mac in self._pending_removals:
                    # removal for this service is already pending
                    return

                _LOGGER.debug("Scheduling removal for %s", name)
                self._pending_removals[mac] = self._hass.async_create_background_task(
                    self._delayed_plug_remove(name, mac),
                    name=f"Removal-Task-For-{name}",
                )
        else:
            _LOGGER.warning(
                "Received request to delete api for gateway with name [%s], but this name"
                "is not associated with an existing PlugAPI. Ignoring... ",
                name,
            )

    async def _delayed_plug_remove(self, name, mac):
        """Actually process the removal after delay."""
        try:
            await asyncio.sleep(self._debounce_seconds)
            _LOGGER.debug(
                "Request to remove plug %s still pending after timeout. Processing remove request... ",
                mac,
            )
            await self.plugs[mac].disconnect()
            del self.plugs[mac]
            del self._known_plug_names[name]
            _LOGGER.info("API for plug %s disconnected and removed. ", mac)
        except asyncio.CancelledError:
            # Task was canceled because service came back
            _LOGGER.debug(
                "Request to remove plug %s was cancelled by request to update, add plug or new message. ",
                mac,
            )
            raise
        finally:
            # Either way were done with this task
            self._pending_removals.pop(mac, None)
