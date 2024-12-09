"""
# Digital Alchemy Synapse Bridge

Bridges are constructed 1-1 with connected applications when they are registered.
All app level interactions are done here, leaving entity changes to other code.

## Heartbeat & availability

Application availability is tracked at the bridge level via 2 mechanisms

1. Explicit messaging: "going offline" & "hello world" type messages
2. Heartbeat detection

> **Note**: heartbeats are NOT the same thing as ping/pong that's part of the HA websocket api

Applications are expected to emit heartbeats no less than every 30 seconds (APP_OFFLINE_DELAY).
If no message is received inside the window, the bridge will flag itself offline (and all associated entities will be unavail).

## Reloading

Reload requests are performed via the event bus.

1. bridge says "describe yourself"
2. app replies with payload
3. bridge unpacks, does some magic (below), then hands off the data HA

> This CAN fail. If the user hits the reload button while the app is not connected, no reply will happen and flow will abort.

## Entity & device management

All entity & device creation / cleanup is done as part of the reload command.

All entities are expected to be associated with some device.
A default application level device will be created, as well as a list of sub devices (associated with primary via_device).

A bridge reload will:
- purge all entities / devices not contained in the payload
- build / update devices
- hand off to HA to do domain/platform (entity) setup

## Auto reload

The bridge likes using the `async_reload` command for it's own config entry in order to trigger rebuilds for itself.
Reasons may include:
- app hash changed (via heartbeat)
- app came online (might be excessive)

The app hash represents the current list of entities reduced to a sha256.
If the list of entities changes at runtime, the hash will change and the integration will request a reload to process update.
"""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CONFIGURATION_URL,
    ATTR_HW_VERSION,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SERIAL_NUMBER,
    ATTR_SUGGESTED_AREA,
    ATTR_SW_VERSION,
    ATTR_VIA_DEVICE,
)
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers import entity_registry as er, device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    DOMAIN,
    PLATFORMS,
    EVENT_NAMESPACE,
    SynapseApplication,
    SynapseMetadata,
    QUERY_TIMEOUT,
    RETRIES,
    RETRY_DELAY,
)
from .helpers import hex_to_object
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant

from .const import DOMAIN, EVENT_NAMESPACE, APP_OFFLINE_DELAY

hashDict = {}


class SynapseBridge:
    """
    - Handle comms with the app (base class)
    - Provide helper methods for entities
    - Create online sensor
    - Tracks app heartbeat
    """
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the bridge"""

        self.logger = logging.getLogger(__name__)
        self.config_entry = config_entry
        self.primary_device = None
        self.via_primary_device = None
        self.hass = hass
        self.app_data: SynapseApplication = config_entry.data
        self.app_name = self.app_data.get("app")
        self.metadata_unique_id = self.app_data.get("unique_id")
        hass.data.setdefault(DOMAIN, {})[self.metadata_unique_id] = self

        self.logger.debug(f"{self.app_name} init bridge")

        self.namespace = EVENT_NAMESPACE
        self.online = False
        self._heartbeat_timer = None
        self._removals = []

        self._listen()

    async def async_cleanup(self) -> None:
        """Called when tearing down the bridge, clean up resources and prepare to go away"""
        self.logger.info(f"{self.app_name} cleanup bridge")
        self._heartbeat_timer.cancel()
        for remove in self._removals:
            remove()

    def event_name(self, event: str) -> str:
        """Standard format for event bus names to keep apps separate"""
        return f"{self.namespace}/{event}/{self.app_name}"

    def _listen(self) -> None:
        """Set up listeners for app level communications. Entity updates use different channels"""
        # The app is expected to emit heartbeat events every 5 seconds or so while online
        self._removals.append(
          self.hass.bus.async_listen(
              self.event_name("heartbeat"),
              self.handle_heartbeat
          )
        )

        # The app is expected to emit shutdown events prior to shutting down (if it can)
        self._removals.append(
          self.hass.bus.async_listen(
              self.event_name("shutdown"),
              self._handle_explicit_shutdown
          )
        )
        self._reset_heartbeat_timer()

    @callback
    def _handle_explicit_shutdown(self, event) -> None:
        """Explicit shutdown events emitted by app"""
        self.logger.info(f"{self.app_name} offline notification")
        # Update entity availability
        self.online = False
        self.hass.bus.async_fire(self.event_name("health"))

        # Heartbeat no longer matters
        if self._heartbeat_timer:
            self._heartbeat_timer.cancel()

    @callback
    def _mark_as_dead(self, event=None) -> None:
        """Timeout on heartbeat"""
        if self.online == False:
            return
        # RIP
        self.logger.warning(f"{self.app_name} lost heartbeat")
        self.online = False
        self.hass.bus.async_fire(self.event_name("health"))

    def _reset_heartbeat_timer(self) -> None:
        """Detected a heartbeat, wait for next"""
        if self._heartbeat_timer:
            self._heartbeat_timer.cancel()
        self._heartbeat_timer = self.hass.loop.call_later(APP_OFFLINE_DELAY, self._mark_as_dead)

    @callback
    def handle_heartbeat(self, event) -> None:
        """Handle heartbeat & "coming back online" messages"""
        # Always (re) start the timer waiting for the next heartbeat
        self._reset_heartbeat_timer()

        if self.online == True:
            return

        # if going from offline -> online
        self.logger.info(f"{self.app_name} restored contact")

        if event is not None and self.app_data is not None:
            if self.metadata_unique_id in hashDict:
                entry_id = self.config_entry.entry_id

                incoming_hash = event.data.get("hash")
                if incoming_hash != hashDict[self.metadata_unique_id]:
                    self.logger.error(f"async_reload {incoming_hash} != {hashDict[self.metadata_unique_id]}")
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(entry_id)
                    )
                    self.logger.error("/async_reload")

        self.online = True
        self.hass.bus.async_fire(self.event_name("health"))


    def format_device_info(self, device = None):
        """Translate between synapse data objects and hass device info"""
        device = device or self.app_data.get("device")
        return {
            ATTR_CONFIGURATION_URL: device.get("configuration_url"),
            ATTR_HW_VERSION: device.get("hw_version"),
            ATTR_IDENTIFIERS: {
                (DOMAIN, device.get("unique_id") or self.metadata_unique_id),
            },
            ATTR_MANUFACTURER: device.get("manufacturer"),
            ATTR_MODEL: device.get("model"),
            ATTR_NAME: device.get("name"),
            ATTR_SERIAL_NUMBER: device.get("serial_number"),
            ATTR_SUGGESTED_AREA: device.get("suggested_area"),
            ATTR_SW_VERSION: device.get("sw_version"),
        }

    async def async_reload(self) -> None:
        """Attach reload call to gather new metadata & update local info"""
        self.logger.debug(f"{self.app_name} request reload")

        # retry a few times - apps attempt reconnect on an interval
        # recent boots will have a short delay before the app can successfully reconnect
        data = await self._async_fetch_state(self.app_name)
        for x in range(0, RETRIES):
            if data is not None:
                self.logger.info(f"{self.app_name} reload success")
                break
            self.logger.warning(f"({x}/{RETRIES}) {self.app_name} reload wait {RETRY_DELAY}s & retry")
            await asyncio.sleep(RETRY_DELAY)
            data = await self._async_fetch_state(self.app_name)

        if data is None:
            self.logger.warning("no response, is app connected?")
            return

        # Handle incoming data
        self.app_data = data
        hashDict[self.metadata_unique_id] = data.get("hash")
        self.app_name = self.app_data.get("app")
        self._refresh_devices()
        self._refresh_entities()

        # this counts as a heartbeat
        self.online = True

    def _refresh_devices(self) -> None:
        """Parse through the incoming payload, and set up devices to match"""
        self.via_primary_device = {}
        expected_device_ids = []
        device_registry = dr.async_get(self.hass)

        # create / update base device
        params = self.format_device_info()
        self.primary_device = DeviceInfo(**params)
        device = device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            **params
        )
        expected_device_ids.append(device.id)

        # if the app declares secondary devices, register them also
        # use via_device to create an association with the base
        secondary_devices: list[SynapseMetadata] = self.app_data.get("secondary_devices",[])


        for device in secondary_devices:
            self.logger.debug(f"{self.app_name} secondary device: {device.get("name")}")

            # create params
            params = self.format_device_info(device)
            params[ATTR_VIA_DEVICE] = (DOMAIN, self.metadata_unique_id)

            # work with registry
            self.via_primary_device[device.get("unique_id")] = DeviceInfo(**params)
            device = device_registry.async_get_or_create(config_entry_id=self.config_entry.entry_id,**params)

            # track as valid id
            expected_device_ids.append(device.id)

        unexpected_devices = []
        for _, device in device_registry.devices.items():
            if device.primary_config_entry == self.config_entry.entry_id:
                if device.id not in expected_device_ids:
                    unexpected_devices.append(device.id)

        for device_id in unexpected_devices:
            self.logger.warning(f"remove {device_id}")
            device_registry.async_remove_device(device_id)

    def _refresh_entities(self) -> None:
        """
        Search out entities to remove: take the list of entities in the incoming payload, diff against current list
        Any unique id that currently exists that shouldn't gets a remove
        """
        entity_registry = er.async_get(self.hass)
        # repeat logic for all domains
        for domain in PLATFORMS:
            incoming_list = self.app_data.get(domain)
            if incoming_list is None:
                continue

            found = []
            for entity in incoming_list:
                found.append(entity.get("unique_id"))

            # removing from inside the loop blows things up
            # create list to run as follow up
            remove = []
            for entity_id, entry in entity_registry.entities.items():
                if entry.platform == "synapse" and entry.config_entry_id == self.config_entry.entry_id:
                    # match based on unique_id, rm by entity_id
                    if entry.unique_id not in found:
                        remove.append(entry.entity_id)

            for entity_id in remove:
                entity_registry.async_remove(entity_id)

    async def _async_fetch_state(self, app: str) -> SynapseApplication:
        """Attach reload call to gather new metadata & update local info"""
        self.hass.bus.async_fire(f"{EVENT_NAMESPACE}/discovery/{app}")
        hex_str = await self._wait_for_reload_reply(f"{EVENT_NAMESPACE}/identify/{app}")
        if hex_str is None:
            return None
        return hex_to_object(hex_str)

    async def _wait_for_reload_reply(self, event_name) -> str:
        """
        Wait for the app to reply, then return.
        Contains short timeout to race reply and return None
        """
        future = asyncio.Future()
        @callback
        def handle_event(event):
            if not future.done():
                future.set_result(event.data["compressed"]) # <<< success value
        self.hass.loop.call_soon_threadsafe(
            self.hass.bus.async_listen_once,
            event_name,
            handle_event
        )
        try:
            return await asyncio.wait_for(future, timeout=QUERY_TIMEOUT)
        except asyncio.TimeoutError:
            return None # <<< error value
