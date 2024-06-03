"""The Xiaomi Bluetooth integration."""

from __future__ import annotations

import logging
from typing import cast

from xiaomi_ble import EncryptionScheme, SensorUpdate, XiaomiBluetoothDeviceData

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    DOMAIN as BLUETOOTH_DOMAIN,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import device_registry as dr
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

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.EVENT, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


def process_service_info(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    data: XiaomiBluetoothDeviceData,
    service_info: BluetoothServiceInfoBleak,
    device_registry: DeviceRegistry,
) -> SensorUpdate:
    """Process a BluetoothServiceInfoBleak, running side effects and returning sensor data."""
    update = data.update(service_info)
    coordinator: XiaomiActiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
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
    # If that payload was encrypted and the bindkey was not verified then we need to reauth
    if (
        not data.pending
        and data.encryption_scheme != EncryptionScheme.NONE
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
    coordinator = hass.data.setdefault(DOMAIN, {})[entry.entry_id] = (
        XiaomiActiveBluetoothProcessorCoordinator(
            hass,
            _LOGGER,
            address=address,
            mode=BluetoothScanningMode.PASSIVE,
            update_method=lambda service_info: process_service_info(
                hass, entry, data, service_info, device_registry
            ),
            needs_poll_method=_needs_poll,
            device_data=data,
            discovered_event_classes=set(
                entry.data.get(CONF_DISCOVERED_EVENT_CLASSES, [])
            ),
            poll_method=_async_poll,
            # We will take advertisements from non-connectable devices
            # since we will trade the BLEDevice for a connectable one
            # if we need to poll it
            connectable=False,
            entry=entry,
        )
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(
        coordinator.async_start()
    )  # only start after all platforms have had a chance to subscribe
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
