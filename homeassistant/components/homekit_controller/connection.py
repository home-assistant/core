"""Helpers for managing a pairing with a HomeKit accessory or bridge."""
import asyncio
import datetime
import logging

from aiohomekit.exceptions import (
    AccessoryDisconnectedError,
    AccessoryNotFoundError,
    EncryptionError,
)
from aiohomekit.model import Accessories
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CHARACTERISTIC_PLATFORMS,
    CONTROLLER,
    DOMAIN,
    ENTITY_MAP,
    HOMEKIT_ACCESSORY_DISPATCH,
)
from .device_trigger import async_fire_triggers, async_setup_triggers_for_entry

DEFAULT_SCAN_INTERVAL = datetime.timedelta(seconds=60)
RETRY_INTERVAL = 60  # seconds
MAX_POLL_FAILURES_TO_DECLARE_UNAVAILABLE = 3

_LOGGER = logging.getLogger(__name__)


def get_accessory_information(accessory):
    """Obtain the accessory information service of a HomeKit device."""
    result = {}
    for service in accessory["services"]:
        stype = service["type"].upper()
        if ServicesTypes.get_short(stype) != "accessory-information":
            continue
        for characteristic in service["characteristics"]:
            ctype = CharacteristicsTypes.get_short(characteristic["type"])
            if "value" in characteristic:
                result[ctype] = characteristic["value"]
    return result


def get_bridge_information(accessories):
    """Return the accessory info for the bridge."""
    for accessory in accessories:
        if accessory["aid"] == 1:
            return get_accessory_information(accessory)
    return get_accessory_information(accessories[0])


def get_accessory_name(accessory_info):
    """Return the name field of an accessory."""
    for field in ("name", "model", "manufacturer"):
        if field in accessory_info:
            return accessory_info[field]
    return None


class HKDevice:
    """HomeKit device."""

    def __init__(self, hass, config_entry, pairing_data):
        """Initialise a generic HomeKit device."""

        self.hass = hass
        self.config_entry = config_entry

        # We copy pairing_data because homekit_python may mutate it, but we
        # don't want to mutate a dict owned by a config entry.
        self.pairing_data = pairing_data.copy()

        self.pairing = hass.data[CONTROLLER].load_pairing(
            self.pairing_data["AccessoryPairingID"], self.pairing_data
        )

        self.accessories = None
        self.config_num = 0

        self.entity_map = Accessories()

        # A list of callbacks that turn HK accessories into entities
        self.accessory_factories = []

        # A list of callbacks that turn HK service metadata into entities
        self.listeners = []

        # A list of callbacks that turn HK characteristics into entities
        self.char_factories = []

        # The platorms we have forwarded the config entry so far. If a new
        # accessory is added to a bridge we may have to load additional
        # platforms. We don't want to load all platforms up front if its just
        # a lightbulb. And we don't want to forward a config entry twice
        # (triggers a Config entry already set up error)
        self.platforms = set()

        # This just tracks aid/iid pairs so we know if a HK service has been
        # mapped to a HA entity.
        self.entities = []

        # A map of aid -> device_id
        # Useful when routing events to triggers
        self.devices = {}

        self.available = False

        self.signal_state_updated = "_".join((DOMAIN, self.unique_id, "state_updated"))

        # Current values of all characteristics homekit_controller is tracking.
        # Key is a (accessory_id, characteristic_id) tuple.
        self.current_state = {}

        self.pollable_characteristics = []

        # If this is set polling is active and can be disabled by calling
        # this method.
        self._polling_interval_remover = None

        # Never allow concurrent polling of the same accessory or bridge
        self._polling_lock = asyncio.Lock()
        self._polling_lock_warned = False
        self._poll_failures = 0

        self.watchable_characteristics = []

        self.pairing.dispatcher_connect(self.process_new_events)

    def add_pollable_characteristics(self, characteristics):
        """Add (aid, iid) pairs that we need to poll."""
        self.pollable_characteristics.extend(characteristics)

    def remove_pollable_characteristics(self, accessory_id):
        """Remove all pollable characteristics by accessory id."""
        self.pollable_characteristics = [
            char for char in self.pollable_characteristics if char[0] != accessory_id
        ]

    def add_watchable_characteristics(self, characteristics):
        """Add (aid, iid) pairs that we need to poll."""
        self.watchable_characteristics.extend(characteristics)
        self.hass.async_create_task(self.pairing.subscribe(characteristics))

    def remove_watchable_characteristics(self, accessory_id):
        """Remove all pollable characteristics by accessory id."""
        self.watchable_characteristics = [
            char for char in self.watchable_characteristics if char[0] != accessory_id
        ]

    @callback
    def async_set_available_state(self, available):
        """Mark state of all entities on this connection when it becomes available or unavailable."""
        _LOGGER.debug(
            "Called async_set_available_state with %s for %s", available, self.unique_id
        )
        if self.available == available:
            return
        self.available = available
        self.hass.helpers.dispatcher.async_dispatcher_send(self.signal_state_updated)

    async def async_setup(self):
        """Prepare to use a paired HomeKit device in Home Assistant."""
        cache = self.hass.data[ENTITY_MAP].get_map(self.unique_id)
        if not cache:
            if await self.async_refresh_entity_map(self.config_num):
                self._polling_interval_remover = async_track_time_interval(
                    self.hass, self.async_update, DEFAULT_SCAN_INTERVAL
                )
                return True
            return False

        self.accessories = cache["accessories"]
        self.config_num = cache["config_num"]

        self.entity_map = Accessories.from_list(self.accessories)

        self._polling_interval_remover = async_track_time_interval(
            self.hass, self.async_update, DEFAULT_SCAN_INTERVAL
        )

        self.hass.async_create_task(self.async_process_entity_map())

        return True

    @callback
    def async_create_devices(self):
        """
        Build device registry entries for all accessories paired with the bridge.

        This is done as well as by the entities for 2 reasons. First, the bridge
        might not have any entities attached to it. Secondly there are stateless
        entities like doorbells and remote controls.
        """
        device_registry = dr.async_get(self.hass)

        devices = {}

        for accessory in self.entity_map.accessories:
            info = accessory.services.first(
                service_type=ServicesTypes.ACCESSORY_INFORMATION,
            )

            device_info = {
                "identifiers": {
                    (
                        DOMAIN,
                        "serial-number",
                        info.value(CharacteristicsTypes.SERIAL_NUMBER),
                    )
                },
                "name": info.value(CharacteristicsTypes.NAME),
                "manufacturer": info.value(CharacteristicsTypes.MANUFACTURER, ""),
                "model": info.value(CharacteristicsTypes.MODEL, ""),
                "sw_version": info.value(CharacteristicsTypes.FIRMWARE_REVISION, ""),
            }

            if accessory.aid == 1:
                # Accessory 1 is the root device (sometimes the only device, sometimes a bridge)
                # Link the root device to the pairing id for the connection.
                device_info["identifiers"].add((DOMAIN, "accessory-id", self.unique_id))
            else:
                # Every pairing has an accessory 1
                # It *doesn't* have a via_device, as it is the device we are connecting to
                # Every other accessory should use it as its via device.
                device_info["via_device"] = (
                    DOMAIN,
                    "serial-number",
                    self.connection_info["serial-number"],
                )

            device = device_registry.async_get_or_create(
                config_entry_id=self.config_entry.entry_id,
                **device_info,
            )

            devices[accessory.aid] = device.id

        self.devices = devices

    async def async_process_entity_map(self):
        """
        Process the entity map and load any platforms or entities that need adding.

        This is idempotent and will be called at startup and when we detect metadata changes
        via the c# counter on the zeroconf record.
        """
        # Ensure the Pairing object has access to the latest version of the entity map. This
        # is especially important for BLE, as the Pairing instance relies on the entity map
        # to map aid/iid to GATT characteristics. So push it to there as well.

        self.pairing.pairing_data["accessories"] = self.accessories

        await self.async_load_platforms()

        self.async_create_devices()

        # Load any triggers for this config entry
        await async_setup_triggers_for_entry(self.hass, self.config_entry)

        self.add_entities()

        if self.watchable_characteristics:
            await self.pairing.subscribe(self.watchable_characteristics)
            if not self.pairing.connection.is_connected:
                return

        await self.async_update()

    async def async_unload(self):
        """Stop interacting with device and prepare for removal from hass."""
        if self._polling_interval_remover:
            self._polling_interval_remover()

        await self.pairing.close()

        return await self.hass.config_entries.async_unload_platforms(
            self.config_entry, self.platforms
        )

    async def async_refresh_entity_map(self, config_num):
        """Handle setup of a HomeKit accessory."""
        try:
            self.accessories = await self.pairing.list_accessories_and_characteristics()
        except AccessoryDisconnectedError:
            # If we fail to refresh this data then we will naturally retry
            # later when Bonjour spots c# is still not up to date.
            return False

        self.entity_map = Accessories.from_list(self.accessories)

        self.hass.data[ENTITY_MAP].async_create_or_update_map(
            self.unique_id, config_num, self.accessories
        )

        self.config_num = config_num
        self.hass.async_create_task(self.async_process_entity_map())

        return True

    def add_accessory_factory(self, add_entities_cb):
        """Add a callback to run when discovering new entities for accessories."""
        self.accessory_factories.append(add_entities_cb)
        self._add_new_entities_for_accessory([add_entities_cb])

    def _add_new_entities_for_accessory(self, handlers):
        for accessory in self.entity_map.accessories:
            for handler in handlers:
                if (accessory.aid, None) in self.entities:
                    continue
                if handler(accessory):
                    self.entities.append((accessory.aid, None))
                    break

    def add_char_factory(self, add_entities_cb):
        """Add a callback to run when discovering new entities for accessories."""
        self.char_factories.append(add_entities_cb)
        self._add_new_entities_for_char([add_entities_cb])

    def _add_new_entities_for_char(self, handlers):
        for accessory in self.entity_map.accessories:
            for service in accessory.services:
                for char in service.characteristics:
                    for handler in handlers:
                        if (accessory.aid, service.iid, char.iid) in self.entities:
                            continue
                        if handler(char):
                            self.entities.append((accessory.aid, service.iid, char.iid))
                            break

    def add_listener(self, add_entities_cb):
        """Add a callback to run when discovering new entities for services."""
        self.listeners.append(add_entities_cb)
        self._add_new_entities([add_entities_cb])

    def add_entities(self):
        """Process the entity map and create HA entities."""
        self._add_new_entities(self.listeners)
        self._add_new_entities_for_accessory(self.accessory_factories)
        self._add_new_entities_for_char(self.char_factories)

    def _add_new_entities(self, callbacks):
        for accessory in self.entity_map.accessories:
            aid = accessory.aid
            for service in accessory.services:
                iid = service.iid

                if (aid, iid) in self.entities:
                    # Don't add the same entity again
                    continue

                for listener in callbacks:
                    if listener(service):
                        self.entities.append((aid, iid))
                        break

    async def async_load_platform(self, platform):
        """Load a single platform idempotently."""
        if platform in self.platforms:
            return

        self.platforms.add(platform)
        try:
            await self.hass.config_entries.async_forward_entry_setup(
                self.config_entry, platform
            )
        except Exception:
            self.platforms.remove(platform)
            raise

    async def async_load_platforms(self):
        """Load any platforms needed by this HomeKit device."""
        tasks = []
        for accessory in self.accessories:
            for service in accessory["services"]:
                stype = ServicesTypes.get_short(service["type"].upper())
                if stype in HOMEKIT_ACCESSORY_DISPATCH:
                    platform = HOMEKIT_ACCESSORY_DISPATCH[stype]
                    if platform not in self.platforms:
                        tasks.append(self.async_load_platform(platform))

                for char in service["characteristics"]:
                    if char["type"].upper() in CHARACTERISTIC_PLATFORMS:
                        platform = CHARACTERISTIC_PLATFORMS[char["type"].upper()]
                        if platform not in self.platforms:
                            tasks.append(self.async_load_platform(platform))

        if tasks:
            await asyncio.gather(*tasks)

    async def async_update(self, now=None):
        """Poll state of all entities attached to this bridge/accessory."""
        if not self.pollable_characteristics:
            self.async_set_available_state(self.pairing.connection.is_connected)
            _LOGGER.debug(
                "HomeKit connection not polling any characteristics: %s", self.unique_id
            )
            return

        if self._polling_lock.locked():
            if not self._polling_lock_warned:
                _LOGGER.warning(
                    "HomeKit controller update skipped as previous poll still in flight: %s",
                    self.unique_id,
                )
                self._polling_lock_warned = True
            return

        if self._polling_lock_warned:
            _LOGGER.info(
                "HomeKit controller no longer detecting back pressure - not skipping poll: %s",
                self.unique_id,
            )
            self._polling_lock_warned = False

        async with self._polling_lock:
            _LOGGER.debug("Starting HomeKit controller update: %s", self.unique_id)

            try:
                new_values_dict = await self.get_characteristics(
                    self.pollable_characteristics
                )
            except AccessoryNotFoundError:
                # Not only did the connection fail, but also the accessory is not
                # visible on the network.
                self.async_set_available_state(False)
                return
            except (AccessoryDisconnectedError, EncryptionError):
                # Temporary connection failure. Device may still available but our
                # connection was dropped or we are reconnecting
                self._poll_failures += 1
                if self._poll_failures >= MAX_POLL_FAILURES_TO_DECLARE_UNAVAILABLE:
                    self.async_set_available_state(False)
                return

            self._poll_failures = 0
            self.process_new_events(new_values_dict)

            _LOGGER.debug("Finished HomeKit controller update: %s", self.unique_id)

    def process_new_events(self, new_values_dict):
        """Process events from accessory into HA state."""
        self.async_set_available_state(True)

        # Process any stateless events (via device_triggers)
        async_fire_triggers(self, new_values_dict)

        for (aid, cid), value in new_values_dict.items():
            accessory = self.current_state.setdefault(aid, {})
            accessory[cid] = value

        # self.current_state will be replaced by entity_map in a future PR
        # For now we update both
        self.entity_map.process_changes(new_values_dict)

        self.hass.helpers.dispatcher.async_dispatcher_send(self.signal_state_updated)

    async def get_characteristics(self, *args, **kwargs):
        """Read latest state from homekit accessory."""
        return await self.pairing.get_characteristics(*args, **kwargs)

    async def put_characteristics(self, characteristics):
        """Control a HomeKit device state from Home Assistant."""
        results = await self.pairing.put_characteristics(characteristics)

        # Feed characteristics back into HA and update the current state
        # results will only contain failures, so anythin in characteristics
        # but not in results was applied successfully - we can just have HA
        # reflect the change immediately.

        new_entity_state = {}
        for aid, iid, value in characteristics:
            key = (aid, iid)

            # If the key was returned by put_characteristics() then the
            # change didn't work
            if key in results:
                continue

            # Otherwise it was accepted and we can apply the change to
            # our state
            new_entity_state[key] = {"value": value}

        self.process_new_events(new_entity_state)

    @property
    def unique_id(self):
        """
        Return a unique id for this accessory or bridge.

        This id is random and will change if a device undergoes a hard reset.
        """
        return self.pairing_data["AccessoryPairingID"]

    @property
    def connection_info(self):
        """Return accessory information for the main accessory."""
        return get_bridge_information(self.accessories)

    @property
    def name(self):
        """Name of the bridge accessory."""
        return get_accessory_name(self.connection_info) or self.unique_id
