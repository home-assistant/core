"""The Xiaomi Bluetooth integration."""

from functools import partial
import logging
from typing import cast

from xiaomi_ble import EncryptionScheme, SensorUpdate, XiaomiBluetoothDeviceData
from xiaomi_ble.devices import S400_MODELS

from homeassistant.components.bluetooth import (
    DOMAIN as BLUETOOTH_DOMAIN,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
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

    Version 1.2 corrects the unique_ids of the S400 impedance sensors.

    The xiaomi-ble library used to mislabel the two impedance measurements
    reported by the Mi Body Composition Scale S400:

    - "impedance" (legacy, generic) actually held the 50 kHz (low frequency)
      measurement.
    - "impedance_low" actually held the 250 kHz (high frequency) measurement.

    The library was corrected so that:

    - "impedance_low" now correctly holds the 50 kHz (low frequency) value.
    - "impedance_high" now correctly holds the 250 kHz (high frequency) value.

    We rename the existing entities' unique_ids to match, so history and
    long-term statistics stay attached to the right entity instead of being
    lost on a disabled leftover. This only applies to the S400; other
    scales (V1/V2) never had this mislabeling and are left untouched.

    The rename must happen in this order: "impedance_low" -> "impedance_high"
    first, to free up the "impedance_low" suffix before the legacy
    "impedance" entity is moved onto it.
    """
    if entry.version == 1 and entry.minor_version == 1:
        address = entry.unique_id
        if address is not None:
            device_registry = dr.async_get(hass)
            device_entry = device_registry.async_get_device(
                identifiers={(BLUETOOTH_DOMAIN, address)}
            )
            if device_entry is not None and device_entry.model in S400_MODELS:
                entity_registry = er.async_get(hass)

                old_low_id = f"{address}-impedance_low"
                new_high_id = f"{address}-impedance_high"
                if entity_id := entity_registry.async_get_entity_id(
                    Platform.SENSOR, DOMAIN, old_low_id
                ):
                    _LOGGER.debug("S400 migration: %s -> %s", old_low_id, new_high_id)
                    entity_registry.async_update_entity(
                        entity_id, new_unique_id=new_high_id
                    )

                old_legacy_id = f"{address}-impedance"
                new_low_id = f"{address}-impedance_low"
                if entity_id := entity_registry.async_get_entity_id(
                    Platform.SENSOR, DOMAIN, old_legacy_id
                ):
                    _LOGGER.debug("S400 migration: %s -> %s", old_legacy_id, new_low_id)
                    entity_registry.async_update_entity(
                        entity_id, new_unique_id=new_low_id
                    )

        hass.config_entries.async_update_entry(entry, minor_version=2)

    return True


def _async_purge_phantom_s400_impedance_entity(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Remove a phantom legacy S400 impedance entity, if one reappeared.

    The unique_id migration in async_migrate_entry renames the legacy
    "-impedance" entity away once, for good: after that, this key should
    never be legitimate again for an S400 device.

    However, Bluetooth passive entities are also restored from a separate
    cache (homeassistant.components.bluetooth.passive_update_processor's
    own storage, keyed by config_entry_id), independent from the entity
    registry. On instances that ran an older version of this integration
    (before the xiaomi-ble fix), that cache still remembers an entity
    description for the old generic "impedance" key. Since the entity
    registry entry for that unique_id was already renamed away, the
    passive processor recreates a brand new (and empty/phantom) entity for
    it every time the platform is set up, before any fresh advertisement
    is even parsed.

    This entity never holds any real history (it's freshly created each
    time), so unlike the legacy entity handled by the migration, it's
    safe to simply remove it here, every setup, until the underlying
    passive-processor cache eventually stops replaying the stale key.
    """
    address = entry.unique_id
    if address is None:
        return

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(BLUETOOTH_DOMAIN, address)}
    )
    if device_entry is None or device_entry.model not in S400_MODELS:
        return

    entity_registry = er.async_get(hass)
    legacy_unique_id = f"{address}-impedance"
    if entity_id := entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, legacy_unique_id
    ):
        _LOGGER.debug("Removing phantom S400 legacy impedance entity: %s", entity_id)
        entity_registry.async_remove(entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Xiaomi BLE device from a config entry."""
    address = entry.unique_id
    assert address is not None

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
