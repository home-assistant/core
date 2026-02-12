"""The BTHome Bluetooth integration."""

from __future__ import annotations

from functools import partial
import logging

from bthome_ble import BTHomeBluetoothDeviceData, SensorUpdate
from bthome_ble.parser import EncryptionScheme

from homeassistant.components.bluetooth import (
    DOMAIN as BLUETOOTH_DOMAIN,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceRegistry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util.signal_type import SignalType

from .const import (
    BTHOME_BLE_EVENT,
    CONF_BINDKEY,
    CONF_DISCOVERED_EVENT_CLASSES,
    CONF_SLEEPY_DEVICE,
    DOMAIN,
    BTHomeBleEvent,
)
from .coordinator import BTHomePassiveBluetoothProcessorCoordinator
from .types import BTHomeConfigEntry

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.EVENT, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


def get_encryption_issue_id(entry_id: str) -> str:
    """Return the repair issue id for encryption removal."""
    return f"encryption_removed_{entry_id}"


def _async_create_encryption_downgrade_issue(
    hass: HomeAssistant, entry: BTHomeConfigEntry, issue_id: str
) -> None:
    """Create a repair issue for encryption downgrade."""
    _LOGGER.warning(
        "BTHome device %s was previously encrypted but is now sending "
        "unencrypted data. This could be a spoofing attempt. "
        "Data will be ignored until resolved",
        entry.title,
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="encryption_removed",
        translation_placeholders={"name": entry.title},
        data={"entry_id": entry.entry_id},
    )


def _async_clear_encryption_downgrade_issue(
    hass: HomeAssistant, entry: BTHomeConfigEntry, issue_id: str
) -> None:
    """Clear the encryption downgrade repair issue."""
    ir.async_delete_issue(hass, DOMAIN, issue_id)
    _LOGGER.info(
        "BTHome device %s is now sending encrypted data again. Resuming normal operation",
        entry.title,
    )


def process_service_info(
    hass: HomeAssistant,
    entry: BTHomeConfigEntry,
    device_registry: DeviceRegistry,
    service_info: BluetoothServiceInfoBleak,
) -> SensorUpdate:
    """Process a BluetoothServiceInfoBleak, running side effects and returning sensor data."""
    coordinator = entry.runtime_data
    data = coordinator.device_data
    issue_registry = ir.async_get(hass)
    issue_id = get_encryption_issue_id(entry.entry_id)
    update = data.update(service_info)

    # Block unencrypted payloads for devices that were previously verified as encrypted.
    if entry.data.get(CONF_BINDKEY) and data.downgrade_detected:
        if not coordinator.encryption_downgrade_logged:
            coordinator.encryption_downgrade_logged = True
            if not issue_registry.async_get_issue(DOMAIN, issue_id):
                _async_create_encryption_downgrade_issue(hass, entry, issue_id)
        return SensorUpdate(title=None, devices={})

    if data.bindkey_verified and (
        (existing_issue := issue_registry.async_get_issue(DOMAIN, issue_id))
        or coordinator.encryption_downgrade_logged
    ):
        coordinator.encryption_downgrade_logged = False
        if existing_issue:
            _async_clear_encryption_downgrade_issue(hass, entry, issue_id)

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

            ble_event = BTHomeBleEvent(
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

            hass.bus.async_fire(BTHOME_BLE_EVENT, ble_event)
            async_dispatcher_send(
                hass,
                format_event_dispatcher_name(address, event_class),
                ble_event,
            )

    # If payload is encrypted and the bindkey is not verified then we need to reauth
    if data.encryption_scheme != EncryptionScheme.NONE and not data.bindkey_verified:
        entry.async_start_reauth(hass, data={"device": data})

    return update


def format_event_dispatcher_name(
    address: str, event_class: str
) -> SignalType[BTHomeBleEvent]:
    """Format an event dispatcher name."""
    return SignalType(f"{DOMAIN}_event_{address}_{event_class}")


def format_discovered_event_class(address: str) -> SignalType[str, BTHomeBleEvent]:
    """Format a discovered event class."""
    return SignalType(f"{DOMAIN}_discovered_event_class_{address}")


async def async_setup_entry(hass: HomeAssistant, entry: BTHomeConfigEntry) -> bool:
    """Set up BTHome Bluetooth from a config entry."""
    address = entry.unique_id
    assert address is not None

    kwargs = {}
    if bindkey := entry.data.get(CONF_BINDKEY):
        kwargs[CONF_BINDKEY] = bytes.fromhex(bindkey)
    data = BTHomeBluetoothDeviceData(**kwargs)

    device_registry = dr.async_get(hass)
    event_classes = set(entry.data.get(CONF_DISCOVERED_EVENT_CLASSES, ()))
    coordinator = BTHomePassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.PASSIVE,
        update_method=partial(process_service_info, hass, entry, device_registry),
        device_data=data,
        discovered_event_classes=event_classes,
        connectable=False,
        entry=entry,
    )
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # only start after all platforms have had a chance to subscribe
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BTHomeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: BTHomeConfigEntry) -> None:
    """Remove a config entry."""
    ir.async_delete_issue(hass, DOMAIN, get_encryption_issue_id(entry.entry_id))
