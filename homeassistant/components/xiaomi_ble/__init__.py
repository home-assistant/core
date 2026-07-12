"""The Xiaomi Bluetooth integration."""

from functools import partial
import logging
from typing import Any, cast

from xiaomi_ble import EncryptionScheme, SensorUpdate, XiaomiBluetoothDeviceData
from xiaomi_ble.devices import S400_MODELS

from homeassistant.components.bluetooth import (
    DOMAIN as BLUETOOTH_DOMAIN,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothEntityKey,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceRegistry
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_DISCOVERED_EVENT_CLASSES,
    CONF_SLEEPY_DEVICE,
    DOMAIN,
    XIAOMI_BLE_EVENT,
    XiaomiBleEvent,
)
from .coordinator import XiaomiActiveBluetoothProcessorCoordinator
from .types import XiaomiBLEConfigEntry

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.EVENT, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

DATA_S400_IMPEDANCE_CACHE_PURGED = "s400_impedance_restore_cache_purged"


def process_service_info(
    hass: HomeAssistant,
    entry: XiaomiBLEConfigEntry,
    device_registry: DeviceRegistry,
    service_info: BluetoothServiceInfoBleak,
) -> SensorUpdate:
    """Process a BluetoothServiceInfoBleak and return sensor data."""
    coordinator = entry.runtime_data
    data = coordinator.device_data
    update = data.update(service_info)
    discovered_event_classes = coordinator.discovered_event_classes
    if entry.data.get(CONF_SLEEPY_DEVICE, False) != data.sleepy_device:
        hass.config_entries.async_update_entry(
            entry,
            data=entry.data | {CONF_SLEEPY_DEVICE: data.sleepy_device},
        )
    if update.events:
        address = service_info.device.address
        for device_key, event in update.events.items():
            sensor_device_info = update.devices[device_key.device_id]
            device = device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                connections={(CONNECTION_BLUETOOTH, address)},
                identifiers={(BLUETOOTH_DOMAIN, address)},
                manufacturer=sensor_device_info.manufacturer,
                model=sensor_device_info.model,
                name=sensor_device_info.name,
                sw_version=sensor_device_info.sw_version,
                hw_version=sensor_device_info.hw_version,
            )
            # event_class may be postfixed with a number, ie 'button_2'
            # but if there is only one button then it will be 'button'
            event_class = event.device_key.key
            event_type = event.event_type

            ble_event = XiaomiBleEvent(
                device_id=device.id,
                address=address,
                event_class=event_class,  # ie 'button'
                event_type=event_type,  # ie 'press'
                event_properties=event.event_properties,
            )

            if event_class not in discovered_event_classes:
                discovered_event_classes.add(event_class)
                hass.config_entries.async_update_entry(
                    entry,
                    data=entry.data
                    | {CONF_DISCOVERED_EVENT_CLASSES: list(discovered_event_classes)},
                )
                async_dispatcher_send(
                    hass, format_discovered_event_class(address), event_class, ble_event
                )

            hass.bus.async_fire(XIAOMI_BLE_EVENT, cast(dict, ble_event))
            async_dispatcher_send(
                hass,
                format_event_dispatcher_name(address, event_class),
                ble_event,
            )

    # If device isn't pending we know it has seen at least one broadcast with a payload
    # If that payload was encrypted and the bindkey was
    # not verified then we need to reauth
    if (
        not data.pending
        and data.encryption_scheme is not EncryptionScheme.NONE
        and not data.bindkey_verified
    ):
        entry.async_start_reauth(hass, data={"device": data})

    return update


def format_event_dispatcher_name(address: str, event_class: str) -> str:
    """Format an event dispatcher name."""
    return f"{DOMAIN}_event_{address}_{event_class}"


def format_discovered_event_class(address: str) -> str:
    """Format a discovered event class."""
    return f"{DOMAIN}_discovered_event_class_{address}"


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries to the current version.

    Version 1.2 swaps the S400 impedance unique IDs while preserving
    entity history. Detect the model from the S400-only impedance key,
    falling back to the device registry when only the legacy key
    exists. Rename low to high first to avoid a unique-ID collision.
    """
    if entry.version == 1 and entry.minor_version == 1:
        address = entry.unique_id
        if address is not None:
            entity_registry = er.async_get(hass)

            old_low_id = f"{address}-impedance_low"
            new_high_id = f"{address}-impedance_high"
            low_entity_id = entity_registry.async_get_entity_id(
                Platform.SENSOR, DOMAIN, old_low_id
            )
            is_s400 = low_entity_id is not None

            old_legacy_id = f"{address}-impedance"
            legacy_entity_id = entity_registry.async_get_entity_id(
                Platform.SENSOR, DOMAIN, old_legacy_id
            )

            if not is_s400 and legacy_entity_id is not None:
                device_registry = dr.async_get(hass)
                device_entry = device_registry.async_get_device(
                    identifiers={(BLUETOOTH_DOMAIN, address)}
                )
                is_s400 = device_entry is not None and device_entry.model in S400_MODELS

            if is_s400:
                if low_entity_id:
                    _LOGGER.debug("S400 migration: %s -> %s", old_low_id, new_high_id)
                    entity_registry.async_update_entity(
                        low_entity_id,
                        new_unique_id=new_high_id,
                        original_name="Impedance High",
                    )

                new_low_id = f"{address}-impedance_low"
                if legacy_entity_id:
                    _LOGGER.debug("S400 migration: %s -> %s", old_legacy_id, new_low_id)
                    entity_registry.async_update_entity(
                        legacy_entity_id,
                        new_unique_id=new_low_id,
                        original_name="Impedance Low",
                    )

        hass.config_entries.async_update_entry(entry, minor_version=2)

    return True


def _async_is_known_s400(
    hass: HomeAssistant,
    address: str,
    coordinator: XiaomiActiveBluetoothProcessorCoordinator | None = None,
) -> bool:
    """Return whether registry, restore data, or model identifies an S400."""
    entity_registry = er.async_get(hass)
    if any(
        entity_registry.async_get_entity_id(Platform.SENSOR, DOMAIN, f"{address}-{key}")
        is not None
        for key in ("impedance_low", "impedance_high")
    ):
        return True

    if coordinator is not None:
        sensor_restore_data = coordinator.restore_data.get(Platform.SENSOR)
        if sensor_restore_data is not None:
            descriptions = sensor_restore_data.get("entity_descriptions", {})
            if any(
                PassiveBluetoothEntityKey(key=key, device_id=None).to_string()
                in descriptions
                for key in ("impedance_low", "impedance_high")
            ):
                return True

    device_entry = dr.async_get(hass).async_get_device(
        identifiers={(BLUETOOTH_DOMAIN, address)}
    )
    return device_entry is not None and device_entry.model in S400_MODELS


def _async_purge_stale_s400_impedance_restore_cache(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: XiaomiActiveBluetoothProcessorCoordinator,
) -> None:
    """Drop stale, mislabeled S400 impedance values from the restore cache.

    The bluetooth passive-processor restore cache is keyed purely by the
    entity_key string the library emits, independent of the entity
    registry -- so a value cached under the old, buggy "impedance_low"
    mapping (250 kHz) would otherwise be restored into the entity that
    now correctly means "impedance_low" (50 kHz). Must run exactly once
    per config entry, before live advertisements repopulate the cache
    with correctly labeled data that must not be discarded afterwards.

    Known limitation: the "done" marker is persisted through the config
    entry store (saved ~1s after a change), while this in-memory edit to
    coordinator.restore_data only reaches disk via the bluetooth
    integration's own passive-processor storage, saved every 15 minutes
    or at a graceful shutdown. Home Assistant exposes no API to force an
    immediate, coupled save of both, so a crash in that window can
    persist the marker without the purge. The next startup would then
    skip purging and briefly restore the stale value -- self-correcting
    on the next scale reading, same as the ordinary purge outcome.
    """
    if entry.data.get(DATA_S400_IMPEDANCE_CACHE_PURGED):
        return

    address = entry.unique_id
    if address is not None and _async_is_known_s400(hass, address, coordinator):
        _purge_stale_sensor_restore_keys(coordinator)

    hass.config_entries.async_update_entry(
        entry,
        data=entry.data | {DATA_S400_IMPEDANCE_CACHE_PURGED: True},
    )


def _purge_stale_sensor_restore_keys(
    coordinator: XiaomiActiveBluetoothProcessorCoordinator,
) -> None:
    """Drop the stale "impedance" and "impedance_low" restore-cache entries."""
    sensor_restore_data = coordinator.restore_data.get(Platform.SENSOR)
    if sensor_restore_data is None:
        return

    stale_keys = (
        PassiveBluetoothEntityKey(key="impedance", device_id=None).to_string(),
        PassiveBluetoothEntityKey(key="impedance_low", device_id=None).to_string(),
    )
    restore_buckets: tuple[tuple[str, dict[str, Any]], ...] = (
        ("entity_data", sensor_restore_data["entity_data"]),
        ("entity_descriptions", sensor_restore_data["entity_descriptions"]),
        ("entity_names", sensor_restore_data["entity_names"]),
    )
    for stale_key in stale_keys:
        for bucket_name, bucket in restore_buckets:
            if bucket.pop(stale_key, None) is not None:
                _LOGGER.debug(
                    "Purged stale S400 impedance restore cache entry: %s.%s",
                    bucket_name,
                    stale_key,
                )


def _async_recover_interrupted_s400_migration(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Finish an S400 unique_id rename left incomplete by a crash.

    HA never retries async_migrate_entry once minor_version already
    reads as current, so an attempt interrupted between the config
    entry's fast save and the entity registry's much slower one (see
    _async_purge_phantom_s400_impedance_entity) would otherwise never
    complete. Safe to run on every setup: a lingering legacy
    "-impedance" entity is the sole trigger, so this never touches an
    already-consistent or genuinely fresh S400.
    """
    if entry.version != 1 or entry.minor_version < 2:
        return

    address = entry.unique_id
    if address is None:
        return

    entity_registry = er.async_get(hass)
    old_legacy_id = f"{address}-impedance"
    legacy_entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, old_legacy_id
    )
    if legacy_entity_id is None or not _async_is_known_s400(hass, address):
        return

    old_low_id = f"{address}-impedance_low"
    new_high_id = f"{address}-impedance_high"
    low_entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, old_low_id
    )
    low_entity = (
        entity_registry.async_get(low_entity_id) if low_entity_id is not None else None
    )
    if low_entity_id is not None and low_entity is not None:
        if low_entity.previous_unique_id != old_legacy_id:
            _LOGGER.debug("S400 migration recovery: %s -> %s", old_low_id, new_high_id)
            entity_registry.async_update_entity(
                low_entity_id,
                new_unique_id=new_high_id,
                original_name="Impedance High",
            )

    new_low_id = f"{address}-impedance_low"
    _LOGGER.debug("S400 migration recovery: %s -> %s", old_legacy_id, new_low_id)
    entity_registry.async_update_entity(
        legacy_entity_id, new_unique_id=new_low_id, original_name="Impedance Low"
    )


def _async_purge_phantom_s400_impedance_entity(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Remove a phantom legacy S400 impedance entity, if one reappeared.

    Bluetooth passive entities restore their last known value from their
    own cache, independent of the entity registry (see
    _async_purge_stale_s400_impedance_restore_cache), which can recreate
    an empty "-impedance" entity on instances that had the pre-fix
    generic sensor. It never holds real history, so it's safe to remove
    on sight -- but only once _async_recover_interrupted_s400_migration
    has had a chance to run first, since a lingering "-impedance" entity
    is otherwise indistinguishable from one whose rename was interrupted
    by a crash and is still awaiting recovery.
    """
    if entry.version != 1 or entry.minor_version < 2:
        return

    address = entry.unique_id
    if address is None:
        return

    entity_registry = er.async_get(hass)
    legacy_unique_id = f"{address}-impedance"

    high_entity_exists = (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{address}-impedance_high"
        )
        is not None
    )
    low_entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{address}-impedance_low"
    )
    low_entity = (
        entity_registry.async_get(low_entity_id) if low_entity_id is not None else None
    )
    renamed_entity_exists = high_entity_exists or (
        low_entity is not None and low_entity.previous_unique_id == legacy_unique_id
    )
    if not renamed_entity_exists:
        return

    if entity_id := entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, legacy_unique_id
    ):
        _LOGGER.debug("Removing phantom S400 legacy impedance entity: %s", entity_id)
        entity_registry.async_remove(entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Xiaomi BLE device from a config entry."""
    address = entry.unique_id
    assert address is not None
    _async_recover_interrupted_s400_migration(hass, entry)

    kwargs = {}
    if bindkey := entry.data.get("bindkey"):
        kwargs["bindkey"] = bytes.fromhex(bindkey)
    data = XiaomiBluetoothDeviceData(**kwargs)

    def _needs_poll(
        service_info: BluetoothServiceInfoBleak, last_poll: float | None
    ) -> bool:
        # Only poll if hass is running, we need to poll,
        # and we actually have a way to connect to the device
        return (
            hass.state is CoreState.running
            and data.poll_needed(service_info, last_poll)
            and bool(
                async_ble_device_from_address(
                    hass, service_info.device.address, connectable=True
                )
            )
        )

    async def _async_poll(service_info: BluetoothServiceInfoBleak) -> SensorUpdate:
        # BluetoothServiceInfoBleak is defined in HA, otherwise would just pass it
        # directly to the Xiaomi code
        # Make sure the device we have is one that we can connect with
        # in case its coming from a passive scanner
        if service_info.connectable:
            connectable_device = service_info.device
        elif device := async_ble_device_from_address(
            hass, service_info.device.address, True
        ):
            connectable_device = device
        else:
            # We have no bluetooth controller that is in range of
            # the device to poll it
            raise RuntimeError(
                f"No connectable device found for {service_info.device.address}"
            )
        return await data.async_poll(connectable_device)

    device_registry = dr.async_get(hass)

    coordinator = XiaomiActiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.PASSIVE,
        update_method=partial(process_service_info, hass, entry, device_registry),
        needs_poll_method=_needs_poll,
        device_data=data,
        discovered_event_classes=set(entry.data.get(CONF_DISCOVERED_EVENT_CLASSES, [])),
        poll_method=_async_poll,
        # We will take advertisements from non-connectable devices
        # since we will trade the BLEDevice for a connectable one
        # if we need to poll it
        connectable=False,
        entry=entry,
    )
    entry.runtime_data = coordinator
    # Must run before async_forward_entry_setups: that call is what makes
    # the sensor platform register its processor and consume
    # coordinator.restore_data, so any stale entries need to be gone first.
    _async_purge_stale_s400_impedance_restore_cache(hass, entry, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # The sensor platform may have just recreated a phantom legacy
    # "impedance" entity from a stale bluetooth passive-processor restore
    # cache (see _async_purge_phantom_s400_impedance_entity). Clean it up
    # now that platform setup has had a chance to (re)create it.
    _async_purge_phantom_s400_impedance_entity(hass, entry)
    # only start after all platforms have had a chance to subscribe
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: XiaomiBLEConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
