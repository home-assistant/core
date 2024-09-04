"""Helpers for managing a pairing with a HomeKit accessory or bridge."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta
from functools import partial
import logging
from operator import attrgetter
from types import MappingProxyType
from typing import Any

from aiohomekit import Controller
from aiohomekit.controller import TransportType
from aiohomekit.exceptions import (
    AccessoryDisconnectedError,
    AccessoryNotFoundError,
    EncryptionError,
)
from aiohomekit.model import Accessories, Accessory, Transport
from aiohomekit.model.characteristics import Characteristic, CharacteristicsTypes
from aiohomekit.model.services import Service, ServicesTypes

from homeassistant.components.thread.dataset_store import async_get_preferred_dataset
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_VIA_DEVICE, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CALLBACK_TYPE, CoreState, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from .config_flow import normalize_hkid
from .const import (
    CHARACTERISTIC_PLATFORMS,
    CONTROLLER,
    DEBOUNCE_COOLDOWN,
    DOMAIN,
    HOMEKIT_ACCESSORY_DISPATCH,
    IDENTIFIER_ACCESSORY_ID,
    IDENTIFIER_LEGACY_ACCESSORY_ID,
    IDENTIFIER_LEGACY_SERIAL_NUMBER,
    IDENTIFIER_SERIAL_NUMBER,
    STARTUP_EXCEPTIONS,
    SUBSCRIBE_COOLDOWN,
)
from .device_trigger import async_fire_triggers, async_setup_triggers_for_entry
from .utils import IidTuple, unique_id_to_iids

RETRY_INTERVAL = 60  # seconds
MAX_POLL_FAILURES_TO_DECLARE_UNAVAILABLE = 3


BLE_AVAILABILITY_CHECK_INTERVAL = 1800  # seconds

_LOGGER = logging.getLogger(__name__)

type AddAccessoryCb = Callable[[Accessory], bool]
type AddServiceCb = Callable[[Service], bool]
type AddCharacteristicCb = Callable[[Characteristic], bool]


def valid_serial_number(serial: str) -> bool:
    """Return if the serial number appears to be valid."""
    if not serial:
        return False
    try:
        return float("".join(serial.rsplit(".", 1))) > 1
    except ValueError:
        return True


class HKDevice:
    """HomeKit device."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        pairing_data: MappingProxyType[str, Any],
    ) -> None:
        """Initialise a generic HomeKit device."""

        self.hass = hass
        self.config_entry = config_entry

        # We copy pairing_data because homekit_python may mutate it, but we
        # don't want to mutate a dict owned by a config entry.
        self.pairing_data = pairing_data.copy()

        connection: Controller = hass.data[CONTROLLER]

        self.pairing = connection.load_pairing(self.unique_id, self.pairing_data)

        # A list of callbacks that turn HK accessories into entities
        self.accessory_factories: list[AddAccessoryCb] = []

        # A list of callbacks that turn HK service metadata into entities
        self.listeners: list[AddServiceCb] = []

        # A list of callbacks that turn HK service metadata into triggers
        self.trigger_factories: list[AddServiceCb] = []

        # Track aid/iid pairs so we know if we already handle triggers for a HK
        # service.
        self._triggers: set[tuple[int, int]] = set()

        # A list of callbacks that turn HK characteristics into entities
        self.char_factories: list[AddCharacteristicCb] = []

        # The platforms we have forwarded the config entry so far. If a new
        # accessory is added to a bridge we may have to load additional
        # platforms. We don't want to load all platforms up front if its just
        # a lightbulb. And we don't want to forward a config entry twice
        # (triggers a Config entry already set up error)
        self.platforms: set[str] = set()

        # This just tracks aid/iid pairs so we know if a HK service has been
        # mapped to a HA entity.
        self.entities: set[tuple[int, int | None, int | None]] = set()

        # A map of aid -> device_id
        # Useful when routing events to triggers
        self.devices: dict[int, str] = {}

        self.available = False

        self.pollable_characteristics: set[tuple[int, int]] = set()

        # Never allow concurrent polling of the same accessory or bridge
        self._polling_lock = asyncio.Lock()
        self._polling_lock_warned = False
        self._poll_failures = 0

        # This is set to True if we can't rely on serial numbers to be unique
        self.unreliable_serial_numbers = False

        self.watchable_characteristics: set[tuple[int, int]] = set()

        self._debounced_update = Debouncer(
            hass,
            _LOGGER,
            cooldown=DEBOUNCE_COOLDOWN,
            immediate=False,
            function=self.async_update,
            background=True,
        )

        self._availability_callbacks: set[CALLBACK_TYPE] = set()
        self._config_changed_callbacks: set[CALLBACK_TYPE] = set()
        self._subscriptions: dict[tuple[int, int], set[CALLBACK_TYPE]] = {}
        self._pending_subscribes: set[tuple[int, int]] = set()
        self._subscribe_timer: CALLBACK_TYPE | None = None
        self._load_platforms_lock = asyncio.Lock()
        self._full_update_requested: bool = False

    @property
    def entity_map(self) -> Accessories:
        """Return the accessories from the pairing."""
        return self.pairing.accessories_state.accessories

    @property
    def config_num(self) -> int:
        """Return the config num from the pairing."""
        return self.pairing.accessories_state.config_num

    def add_pollable_characteristics(
        self, characteristics: list[tuple[int, int]]
    ) -> None:
        """Add (aid, iid) pairs that we need to poll."""
        self.pollable_characteristics.update(characteristics)

    def remove_pollable_characteristics(
        self, characteristics: list[tuple[int, int]]
    ) -> None:
        """Remove all pollable characteristics by accessory id."""
        for aid_iid in characteristics:
            self.pollable_characteristics.discard(aid_iid)

    def add_watchable_characteristics(
        self, characteristics: list[tuple[int, int]]
    ) -> None:
        """Add (aid, iid) pairs that we need to poll."""
        self.watchable_characteristics.update(characteristics)
        self._pending_subscribes.update(characteristics)
        # Try to subscribe to the characteristics all at once
        if not self._subscribe_timer:
            self._subscribe_timer = async_call_later(
                self.hass,
                SUBSCRIBE_COOLDOWN,
                self._async_subscribe,
            )

    @callback
    def _async_cancel_subscription_timer(self) -> None:
        """Cancel the subscribe timer."""
        if self._subscribe_timer:
            self._subscribe_timer()
            self._subscribe_timer = None

    @callback
    def _async_subscribe(self, _now: datetime) -> None:
        """Subscribe to characteristics."""
        self._subscribe_timer = None
        if self._pending_subscribes:
            subscribes = self._pending_subscribes.copy()
            self._pending_subscribes.clear()
            self.config_entry.async_create_task(
                self.hass,
                self.pairing.subscribe(subscribes),
                name=f"hkc subscriptions {self.unique_id}",
                eager_start=True,
            )

    def remove_watchable_characteristics(
        self, characteristics: list[tuple[int, int]]
    ) -> None:
        """Remove all pollable characteristics by accessory id."""
        for aid_iid in characteristics:
            self.watchable_characteristics.discard(aid_iid)
            self._pending_subscribes.discard(aid_iid)

    @callback
    def async_set_available_state(self, available: bool) -> None:
        """Mark state of all entities on this connection when it becomes available or unavailable."""
        _LOGGER.debug(
            "Called async_set_available_state with %s for %s", available, self.unique_id
        )
        if self.available == available:
            return
        self.available = available
        for callback_ in self._availability_callbacks:
            callback_()

    async def _async_populate_ble_accessory_state(self, event: Event) -> None:
        """Populate the BLE accessory state without blocking startup.

        If the accessory was asleep at startup we need to retry
        since we continued on to allow startup to proceed.

        If this fails the state may be inconsistent, but will
        get corrected as soon as the accessory advertises again.
        """
        self._async_start_polling()
        try:
            await self.pairing.async_populate_accessories_state(force_update=True)
        except STARTUP_EXCEPTIONS as ex:
            _LOGGER.debug(
                (
                    "Failed to populate BLE accessory state for %s, accessory may be"
                    " sleeping and will be retried the next time it advertises: %s"
                ),
                self.config_entry.title,
                ex,
            )

    async def async_setup(self) -> None:
        """Prepare to use a paired HomeKit device in Home Assistant."""
        pairing = self.pairing
        transport = pairing.transport
        entry = self.config_entry

        # We need to force an update here to make sure we have
        # the latest values since the async_update we do in
        # async_process_entity_map will no values to poll yet
        # since entities are added via dispatching and then
        # they add the chars they are concerned about in
        # async_added_to_hass which is too late.
        #
        # Ideally we would know which entities we are about to add
        # so we only poll those chars but that is not possible
        # yet.
        attempts = None if self.hass.state is CoreState.running else 1
        if (
            transport == Transport.BLE
            and pairing.accessories
            and pairing.accessories.has_aid(1)
        ):
            # The GSN gets restored and a catch up poll will be
            # triggered via disconnected events automatically
            # if we are out of sync. To be sure we are in sync;
            # If for some reason the BLE connection failed
            # previously we force an update after startup
            # is complete.
            entry.async_on_unload(
                self.hass.bus.async_listen(
                    EVENT_HOMEASSISTANT_STARTED,
                    self._async_populate_ble_accessory_state,
                )
            )
        else:
            await self.pairing.async_populate_accessories_state(
                force_update=True, attempts=attempts
            )
            self._async_start_polling()

        entry.async_on_unload(pairing.dispatcher_connect(self.process_new_events))
        entry.async_on_unload(
            pairing.dispatcher_connect_config_changed(self.process_config_changed)
        )
        entry.async_on_unload(
            pairing.dispatcher_availability_changed(self.async_set_available_state)
        )
        entry.async_on_unload(self._async_cancel_subscription_timer)

        await self.async_process_entity_map()

        # If everything is up to date, we can create the entities
        # since we know the data is not stale.
        await self.async_add_new_entities()

        self.async_set_available_state(self.pairing.is_available)

        if transport == Transport.BLE:
            # If we are using BLE, we need to periodically check of the
            # BLE device is available since we won't get callbacks
            # when it goes away since we HomeKit supports disconnected
            # notifications and we cannot treat a disconnect as unavailability.
            entry.async_on_unload(
                async_track_time_interval(
                    self.hass,
                    self.async_update_available_state,
                    timedelta(seconds=BLE_AVAILABILITY_CHECK_INTERVAL),
                    name=f"HomeKit Device {self.unique_id} BLE availability "
                    "check poll",
                )
            )
            # BLE devices always get an RSSI sensor as well
            if "sensor" not in self.platforms:
                async with self._load_platforms_lock:
                    await self._async_load_platforms({"sensor"})

    @callback
    def _async_start_polling(self) -> None:
        """Start polling for updates."""
        # We use async_request_update to avoid multiple updates
        # at the same time which would generate a spurious warning
        # in the log about concurrent polling.
        self.config_entry.async_on_unload(
            async_track_time_interval(
                self.hass,
                self._async_schedule_update,
                self.pairing.poll_interval,
                name=f"HomeKit Device {self.unique_id} availability check poll",
            )
        )

    @callback
    def _async_schedule_update(self, now: datetime) -> None:
        """Schedule an update."""
        self.config_entry.async_create_background_task(
            self.hass,
            self._debounced_update.async_call(),
            name=f"hkc {self.unique_id} alive poll",
            eager_start=True,
        )

    async def async_add_new_entities(self) -> None:
        """Add new entities to Home Assistant."""
        await self.async_load_platforms()
        self.add_entities()

    def device_info_for_accessory(self, accessory: Accessory) -> DeviceInfo:
        """Build a DeviceInfo for a given accessory."""
        identifiers = {
            (
                IDENTIFIER_ACCESSORY_ID,
                f"{self.unique_id}:aid:{accessory.aid}",
            )
        }

        if not self.unreliable_serial_numbers:
            identifiers.add((IDENTIFIER_SERIAL_NUMBER, accessory.serial_number))

        device_info = DeviceInfo(
            identifiers={
                (
                    IDENTIFIER_ACCESSORY_ID,
                    f"{self.unique_id}:aid:{accessory.aid}",
                )
            },
            name=accessory.name,
            manufacturer=accessory.manufacturer,
            model=accessory.model,
            sw_version=accessory.firmware_revision,
            hw_version=accessory.hardware_revision,
            serial_number=accessory.serial_number,
        )

        if accessory.aid != 1:
            # Every pairing has an accessory 1
            # It *doesn't* have a via_device, as it is the device we are connecting to
            # Every other accessory should use it as its via device.
            device_info[ATTR_VIA_DEVICE] = (
                IDENTIFIER_ACCESSORY_ID,
                f"{self.unique_id}:aid:1",
            )

        return device_info

    @callback
    def async_migrate_devices(self) -> None:
        """Migrate legacy device entries from 3-tuples to 2-tuples."""
        _LOGGER.debug(
            "Migrating device registry entries for pairing %s", self.unique_id
        )

        device_registry = dr.async_get(self.hass)

        for accessory in self.entity_map.accessories:
            identifiers = {
                (
                    DOMAIN,
                    IDENTIFIER_LEGACY_ACCESSORY_ID,
                    f"{self.unique_id}_{accessory.aid}",
                ),
            }

            if accessory.aid == 1:
                identifiers.add(
                    (DOMAIN, IDENTIFIER_LEGACY_ACCESSORY_ID, self.unique_id)
                )

            if valid_serial_number(accessory.serial_number):
                identifiers.add(
                    (DOMAIN, IDENTIFIER_LEGACY_SERIAL_NUMBER, accessory.serial_number)
                )

            device = device_registry.async_get_device(identifiers=identifiers)  # type: ignore[arg-type]
            if not device:
                continue

            if self.config_entry.entry_id not in device.config_entries:
                _LOGGER.info(
                    (
                        "Found candidate device for %s:aid:%s, but owned by a different"
                        " config entry, skipping"
                    ),
                    self.unique_id,
                    accessory.aid,
                )
                continue

            _LOGGER.info(
                "Migrating device identifiers for %s:aid:%s",
                self.unique_id,
                accessory.aid,
            )
            device_registry.async_update_device(
                device.id,
                new_identifiers={
                    (
                        IDENTIFIER_ACCESSORY_ID,
                        f"{self.unique_id}:aid:{accessory.aid}",
                    )
                },
            )

    @callback
    def async_migrate_unique_id(
        self, old_unique_id: str, new_unique_id: str | None, platform: str
    ) -> None:
        """Migrate legacy unique IDs to new format."""
        assert new_unique_id is not None
        _LOGGER.debug(
            "Checking if unique ID %s on %s needs to be migrated",
            old_unique_id,
            platform,
        )
        entity_registry = er.async_get(self.hass)
        # async_get_entity_id wants the "homekit_controller" domain
        # in the platform field and the actual platform in the domain
        # field for historical reasons since everything used to be
        # PLATFORM.INTEGRATION instead of INTEGRATION.PLATFORM
        if (
            entity_id := entity_registry.async_get_entity_id(
                platform, DOMAIN, old_unique_id
            )
        ) is None:
            _LOGGER.debug("Unique ID %s does not need to be migrated", old_unique_id)
            return
        if new_entity_id := entity_registry.async_get_entity_id(
            platform, DOMAIN, new_unique_id
        ):
            _LOGGER.debug(
                (
                    "Unique ID %s is already in use by %s (system may have been"
                    " downgraded)"
                ),
                new_unique_id,
                new_entity_id,
            )
            return
        _LOGGER.debug(
            "Migrating unique ID for entity %s (%s -> %s)",
            entity_id,
            old_unique_id,
            new_unique_id,
        )
        entity_registry.async_update_entity(entity_id, new_unique_id=new_unique_id)

    @callback
    def async_remove_legacy_device_serial_numbers(self) -> None:
        """Migrate remove legacy serial numbers from devices.

        We no longer use serial numbers as device identifiers
        since they are not reliable, and the HomeKit spec
        does not require them to be stable.
        """
        _LOGGER.debug(
            (
                "Removing legacy serial numbers from device registry entries for"
                " pairing %s"
            ),
            self.unique_id,
        )

        device_registry = dr.async_get(self.hass)
        for accessory in self.entity_map.accessories:
            identifiers = {
                (
                    IDENTIFIER_ACCESSORY_ID,
                    f"{self.unique_id}:aid:{accessory.aid}",
                )
            }
            legacy_serial_identifier = (
                IDENTIFIER_SERIAL_NUMBER,
                accessory.serial_number,
            )

            device = device_registry.async_get_device(identifiers=identifiers)
            if not device or legacy_serial_identifier not in device.identifiers:
                continue

            device_registry.async_update_device(device.id, new_identifiers=identifiers)

    @callback
    def async_reap_stale_entity_registry_entries(self) -> None:
        """Delete entity registry entities for removed characteristics, services and accessories."""
        _LOGGER.debug(
            "Removing stale entity registry entries for pairing %s",
            self.unique_id,
        )

        reg = er.async_get(self.hass)

        # For the current config entry only, visit all registry entity entries
        # Build a set of (unique_id, aid, sid, iid)
        # For services, (unique_id, aid, sid, None)
        # For accessories, (unique_id, aid, None, None)
        entries = er.async_entries_for_config_entry(reg, self.config_entry.entry_id)
        existing_entities = {
            iids: entry.entity_id
            for entry in entries
            if (iids := unique_id_to_iids(entry.unique_id))
        }

        # Process current entity map and produce a similar set
        current_unique_id: set[IidTuple] = set()
        for accessory in self.entity_map.accessories:
            current_unique_id.add((accessory.aid, None, None))

            for service in accessory.services:
                current_unique_id.add((accessory.aid, service.iid, None))

                for char in service.characteristics:
                    if self.pairing.transport != Transport.BLE:
                        if char.type == CharacteristicsTypes.THREAD_CONTROL_POINT:
                            continue

                    current_unique_id.add(
                        (
                            accessory.aid,
                            service.iid,
                            char.iid,
                        )
                    )

        # Remove the difference
        if stale := existing_entities.keys() - current_unique_id:
            for parts in stale:
                _LOGGER.debug(
                    "Removing stale entity registry entry %s for pairing %s",
                    existing_entities[parts],
                    self.unique_id,
                )
                reg.async_remove(existing_entities[parts])

    @callback
    def async_migrate_ble_unique_id(self) -> None:
        """Config entries from step_bluetooth used incorrect identifier for unique_id."""
        unique_id = normalize_hkid(self.unique_id)
        if unique_id != self.config_entry.unique_id:
            _LOGGER.debug(
                "Fixing incorrect unique_id: %s -> %s",
                self.config_entry.unique_id,
                unique_id,
            )
            self.hass.config_entries.async_update_entry(
                self.config_entry, unique_id=unique_id
            )

    @callback
    def async_create_devices(self) -> None:
        """Build device registry entries for all accessories paired with the bridge.

        This is done as well as by the entities for 2 reasons. First, the bridge
        might not have any entities attached to it. Secondly there are stateless
        entities like doorbells and remote controls.
        """
        device_registry = dr.async_get(self.hass)

        devices = {}

        # Accessories need to be created in the correct order or setting up
        # relationships with ATTR_VIA_DEVICE may fail.
        for accessory in sorted(self.entity_map.accessories, key=attrgetter("aid")):
            device_info = self.device_info_for_accessory(accessory)

            device = device_registry.async_get_or_create(
                config_entry_id=self.config_entry.entry_id,
                **device_info,
            )

            devices[accessory.aid] = device.id

        self.devices = devices

    @callback
    def async_detect_workarounds(self) -> None:
        """Detect any workarounds that are needed for this pairing."""
        unreliable_serial_numbers = False

        devices = set()

        for accessory in self.entity_map.accessories:
            if not valid_serial_number(accessory.serial_number):
                _LOGGER.debug(
                    (
                        "Serial number %r is not valid, it cannot be used as a unique"
                        " identifier"
                    ),
                    accessory.serial_number,
                )
                unreliable_serial_numbers = True

            elif accessory.serial_number in devices:
                _LOGGER.debug(
                    (
                        "Serial number %r is duplicated within this pairing, it cannot"
                        " be used as a unique identifier"
                    ),
                    accessory.serial_number,
                )
                unreliable_serial_numbers = True

            elif accessory.serial_number == accessory.hardware_revision:
                # This is a known bug with some devices (e.g. RYSE SmartShades)
                _LOGGER.debug(
                    (
                        "Serial number %r is actually the hardware revision, it cannot"
                        " be used as a unique identifier"
                    ),
                    accessory.serial_number,
                )
                unreliable_serial_numbers = True

            devices.add(accessory.serial_number)

        self.unreliable_serial_numbers = unreliable_serial_numbers

    async def async_process_entity_map(self) -> None:
        """Process the entity map and load any platforms or entities that need adding.

        This is idempotent and will be called at startup and when we detect metadata changes
        via the c# counter on the zeroconf record.
        """
        # Ensure the Pairing object has access to the latest version of the entity map. This
        # is especially important for BLE, as the Pairing instance relies on the entity map
        # to map aid/iid to GATT characteristics. So push it to there as well.
        self.async_detect_workarounds()

        # Migrate to new device ids
        self.async_migrate_devices()

        # Remove any of the legacy serial numbers from the device registry
        self.async_remove_legacy_device_serial_numbers()

        self.async_migrate_ble_unique_id()

        self.async_reap_stale_entity_registry_entries()

        self.async_create_devices()

        # Load any triggers for this config entry
        await async_setup_triggers_for_entry(self.hass, self.config_entry)

    async def async_unload(self) -> None:
        """Stop interacting with device and prepare for removal from hass."""
        await self.pairing.shutdown()

        await self.hass.config_entries.async_unload_platforms(
            self.config_entry, self.platforms
        )

    def process_config_changed(self, config_num: int) -> None:
        """Handle a config change notification from the pairing."""
        self.config_entry.async_create_task(
            self.hass, self.async_update_new_accessories_state(), eager_start=True
        )

    async def async_update_new_accessories_state(self) -> None:
        """Process a change in the pairings accessories state."""
        await self.async_process_entity_map()
        for callback_ in self._config_changed_callbacks:
            callback_()
        await self.async_update()
        await self.async_add_new_entities()

    @callback
    def async_entity_key_removed(
        self, entity_key: tuple[int, int | None, int | None]
    ) -> None:
        """Handle an entity being removed.

        Releases the entity from self.entities so it can be added again.
        """
        self.entities.discard(entity_key)

    def add_accessory_factory(self, add_entities_cb: AddAccessoryCb) -> None:
        """Add a callback to run when discovering new entities for accessories."""
        self.accessory_factories.append(add_entities_cb)
        self._add_new_entities_for_accessory([add_entities_cb])

    def _add_new_entities_for_accessory(self, handlers: list[AddAccessoryCb]) -> None:
        for accessory in self.entity_map.accessories:
            entity_key = (accessory.aid, None, None)
            for handler in handlers:
                if entity_key not in self.entities and handler(accessory):
                    self.entities.add(entity_key)
                    break

    def add_char_factory(self, add_entities_cb: AddCharacteristicCb) -> None:
        """Add a callback to run when discovering new entities for accessories."""
        self.char_factories.append(add_entities_cb)
        self._add_new_entities_for_char([add_entities_cb])

    def _add_new_entities_for_char(self, handlers: list[AddCharacteristicCb]) -> None:
        for accessory in self.entity_map.accessories:
            for service in accessory.services:
                for char in service.characteristics:
                    entity_key = (accessory.aid, service.iid, char.iid)
                    for handler in handlers:
                        if entity_key not in self.entities and handler(char):
                            self.entities.add(entity_key)
                            break

    def add_listener(self, add_entities_cb: AddServiceCb) -> None:
        """Add a callback to run when discovering new entities for services."""
        self.listeners.append(add_entities_cb)
        self._add_new_entities([add_entities_cb])

    def add_trigger_factory(self, add_triggers_cb: AddServiceCb) -> None:
        """Add a callback to run when discovering new triggers for services."""
        self.trigger_factories.append(add_triggers_cb)
        self._add_new_triggers([add_triggers_cb])

    def _add_new_triggers(self, callbacks: list[AddServiceCb]) -> None:
        for accessory in self.entity_map.accessories:
            aid = accessory.aid
            for service in accessory.services:
                iid = service.iid
                entity_key = (aid, iid)

                if entity_key in self._triggers:
                    # Don't add the same trigger again
                    continue

                for add_trigger_cb in callbacks:
                    if add_trigger_cb(service):
                        self._triggers.add(entity_key)
                        break

    def add_entities(self) -> None:
        """Process the entity map and create HA entities."""
        self._add_new_entities(self.listeners)
        self._add_new_entities_for_accessory(self.accessory_factories)
        self._add_new_entities_for_char(self.char_factories)
        self._add_new_triggers(self.trigger_factories)

    def _add_new_entities(self, callbacks: list[AddServiceCb]) -> None:
        for accessory in self.entity_map.accessories:
            aid = accessory.aid
            for service in accessory.services:
                entity_key = (aid, None, service.iid)

                if entity_key in self.entities:
                    # Don't add the same entity again
                    continue

                for listener in callbacks:
                    if listener(service):
                        self.entities.add(entity_key)
                        break

    async def _async_load_platforms(self, platforms: set[str]) -> None:
        """Load a group of platforms."""
        assert self._load_platforms_lock.locked(), "Must be called with lock held"
        if not (to_load := platforms - self.platforms):
            return
        self.platforms.update(to_load)
        await self.hass.config_entries.async_forward_entry_setups(
            self.config_entry, platforms
        )

    async def async_load_platforms(self) -> None:
        """Load any platforms needed by this HomeKit device."""
        async with self._load_platforms_lock:
            to_load: set[str] = set()
            for accessory in self.entity_map.accessories:
                for service in accessory.services:
                    if service.type in HOMEKIT_ACCESSORY_DISPATCH:
                        platform = HOMEKIT_ACCESSORY_DISPATCH[service.type]
                        if platform not in self.platforms:
                            to_load.add(platform)

                    for char in service.characteristics:
                        if char.type in CHARACTERISTIC_PLATFORMS:
                            platform = CHARACTERISTIC_PLATFORMS[char.type]
                            if platform not in self.platforms:
                                to_load.add(platform)

            if to_load:
                await self._async_load_platforms(to_load)

    @callback
    def async_update_available_state(self, *_: Any) -> None:
        """Update the available state of the device."""
        self.async_set_available_state(self.pairing.is_available)

    async def async_request_update(self, now: datetime | None = None) -> None:
        """Request an debounced update from the accessory."""
        self._full_update_requested = True
        await self._debounced_update.async_call()

    async def async_update(self, now: datetime | None = None) -> None:
        """Poll state of all entities attached to this bridge/accessory."""
        to_poll = self.pollable_characteristics
        accessories = self.entity_map.accessories

        if (
            not self._full_update_requested
            and len(accessories) == 1
            and self.available
            and not (to_poll - self.watchable_characteristics)
            and self.pairing.is_available
            and await self.pairing.controller.async_reachable(
                self.unique_id, timeout=5.0
            )
        ):
            # If its a single accessory and all chars are watchable,
            # only poll the firmware version to keep the connection alive
            # https://github.com/home-assistant/core/issues/123412
            #
            # Firmware revision is used here since iOS does this to keep camera
            # connections alive, and the goal is to not regress
            # https://github.com/home-assistant/core/issues/116143
            # by polling characteristics that are not normally polled frequently
            # and may not be tested by the device vendor.
            #
            _LOGGER.debug(
                "Accessory is reachable, limiting poll to firmware version: %s",
                self.unique_id,
            )
            first_accessory = accessories[0]
            accessory_info = first_accessory.services.first(
                service_type=ServicesTypes.ACCESSORY_INFORMATION
            )
            assert accessory_info is not None
            firmware_iid = accessory_info[CharacteristicsTypes.FIRMWARE_REVISION].iid
            to_poll = {(first_accessory.aid, firmware_iid)}

        self._full_update_requested = False

        if not to_poll:
            self.async_update_available_state()
            _LOGGER.debug(
                "HomeKit connection not polling any characteristics: %s", self.unique_id
            )
            return

        if self._polling_lock.locked():
            if not self._polling_lock_warned:
                _LOGGER.warning(
                    (
                        "HomeKit device update skipped as previous poll still in"
                        " flight: %s"
                    ),
                    self.unique_id,
                )
                self._polling_lock_warned = True
            return

        if self._polling_lock_warned:
            _LOGGER.info(
                (
                    "HomeKit device no longer detecting back pressure - not"
                    " skipping poll: %s"
                ),
                self.unique_id,
            )
            self._polling_lock_warned = False

        async with self._polling_lock:
            _LOGGER.debug("Starting HomeKit device update: %s", self.unique_id)

            try:
                new_values_dict = await self.get_characteristics(to_poll)
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

            _LOGGER.debug("Finished HomeKit device update: %s", self.unique_id)

    def process_new_events(
        self, new_values_dict: dict[tuple[int, int], dict[str, Any]]
    ) -> None:
        """Process events from accessory into HA state."""
        self.async_set_available_state(True)

        # Process any stateless events (via device_triggers)
        async_fire_triggers(self, new_values_dict)

        to_callback: set[CALLBACK_TYPE] = set()
        for aid_iid in self.entity_map.process_changes(new_values_dict):
            if callbacks := self._subscriptions.get(aid_iid):
                to_callback.update(callbacks)

        for callback_ in to_callback:
            callback_()

    @callback
    def _remove_characteristics_callback(
        self, characteristics: set[tuple[int, int]], callback_: CALLBACK_TYPE
    ) -> None:
        """Remove a characteristics callback."""
        for aid_iid in characteristics:
            self._subscriptions[aid_iid].remove(callback_)
            if not self._subscriptions[aid_iid]:
                del self._subscriptions[aid_iid]

    @callback
    def async_subscribe(
        self, characteristics: set[tuple[int, int]], callback_: CALLBACK_TYPE
    ) -> CALLBACK_TYPE:
        """Add characteristics to the watch list."""
        for aid_iid in characteristics:
            self._subscriptions.setdefault(aid_iid, set()).add(callback_)
        return partial(
            self._remove_characteristics_callback, characteristics, callback_
        )

    @callback
    def _remove_availability_callback(self, callback_: CALLBACK_TYPE) -> None:
        """Remove an availability callback."""
        self._availability_callbacks.remove(callback_)

    @callback
    def async_subscribe_availability(self, callback_: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Add characteristics to the watch list."""
        self._availability_callbacks.add(callback_)
        return partial(self._remove_availability_callback, callback_)

    @callback
    def _remove_config_changed_callback(self, callback_: CALLBACK_TYPE) -> None:
        """Remove an availability callback."""
        self._config_changed_callbacks.remove(callback_)

    @callback
    def async_subscribe_config_changed(self, callback_: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Subscribe to config of the accessory being changed aka c# changes."""
        self._config_changed_callbacks.add(callback_)
        return partial(self._remove_config_changed_callback, callback_)

    async def get_characteristics(
        self, *args: Any, **kwargs: Any
    ) -> dict[tuple[int, int], dict[str, Any]]:
        """Read latest state from homekit accessory."""
        return await self.pairing.get_characteristics(*args, **kwargs)

    async def put_characteristics(
        self, characteristics: Iterable[tuple[int, int, Any]]
    ) -> None:
        """Control a HomeKit device state from Home Assistant."""
        await self.pairing.put_characteristics(characteristics)

    @property
    def is_unprovisioned_thread_device(self) -> bool:
        """Is this a thread capable device not connected by CoAP."""
        if self.pairing.controller.transport_type != TransportType.BLE:
            return False

        if not self.entity_map.aid(1).services.first(
            service_type=ServicesTypes.THREAD_TRANSPORT
        ):
            return False

        return True

    async def async_thread_provision(self) -> None:
        """Migrate a HomeKit pairing to CoAP (Thread)."""
        if self.pairing.controller.transport_type == TransportType.COAP:
            raise HomeAssistantError("Already connected to a thread network")

        if not (dataset := await async_get_preferred_dataset(self.hass)):
            raise HomeAssistantError("No thread network credentials available")

        await self.pairing.thread_provision(dataset)

        try:
            discovery = (
                await self.hass.data[CONTROLLER]
                .transports[TransportType.COAP]
                .async_find(self.unique_id, timeout=30)
            )
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **self.config_entry.data,
                    "Connection": "CoAP",
                    "AccessoryIP": discovery.description.address,
                    "AccessoryPort": discovery.description.port,
                },
            )
            _LOGGER.debug(
                "%s: Found device on local network, migrating integration to Thread",
                self.unique_id,
            )

        except AccessoryNotFoundError as exc:
            _LOGGER.debug(
                "%s: Failed to appear on local network as a Thread device, reverting to BLE",
                self.unique_id,
            )
            raise HomeAssistantError("Could not migrate device to Thread") from exc

        finally:
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

    @property
    def unique_id(self) -> str:
        """Return a unique id for this accessory or bridge.

        This id is random and will change if a device undergoes a hard reset.
        """
        return self.pairing_data["AccessoryPairingID"]
