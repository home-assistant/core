"""WebSocket API for the LoRaWAN integration."""

import logging
from typing import Any

import probatio

from homeassistant.components import websocket_api
from homeassistant.config_entries import (
    SIGNAL_CONFIG_ENTRY_CHANGED,
    ConfigEntry,
    ConfigEntryChange,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .connection import DATA_REGISTRY
from .const import SIGNAL_DEVICES_CHANGED

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Register the device overview commands."""
    websocket_api.async_register_command(hass, websocket_list_devices)
    websocket_api.async_register_command(hass, websocket_subscribe_devices)


@callback
def _snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Describe devices using current config entries and device registry names."""
    registry = hass.data[DATA_REGISTRY]
    device_registry = dr.async_get(hass)
    vendor_entries_by_brand: dict[tuple[str, int | str | None], list[ConfigEntry]] = {}
    for domain, matchers in registry.integrations.items():
        domain_entries = hass.config_entries.async_entries(domain, include_ignore=False)
        for matcher in matchers:
            vendor_entries_by_brand.setdefault(matcher, []).extend(domain_entries)
    devices = []
    connections = []
    for entry_id, registered in registry.connections.items():
        if (entry := hass.config_entries.async_get_entry(entry_id)) is None:
            continue
        connection = {
            "entry_id": entry_id,
            "domain": entry.domain,
            "title": entry.title,
            "configuration_url": registered.configuration_url,
        }
        connections.append(connection)
        for state in registered.devices.values():
            descriptor = state.descriptor
            vendor_entries = vendor_entries_by_brand.get(
                (descriptor.stack, descriptor.brand_id)
            )
            device = None
            for vendor_entry in vendor_entries or ():
                device = device_registry.async_get_device_by_identifier(
                    (
                        vendor_entry.domain,
                        f"{descriptor.network_id}:{descriptor.dev_eui}",
                    ),
                    vendor_entry.entry_id,
                )
                if device is not None:
                    break
            if device is not None:
                support = "supported"
            elif descriptor.brand_id is None or not descriptor.model_id:
                support = "missing_identity"
            elif vendor_entries == []:
                support = "integration_not_configured"
            else:
                support = "unsupported_model"
            status = state.status
            devices.append(
                {
                    "dev_eui": descriptor.dev_eui,
                    "name": ((device.name_by_user or device.name) if device else None)
                    or descriptor.name
                    or descriptor.dev_eui,
                    "manufacturer": (device.manufacturer if device else None)
                    or descriptor.manufacturer,
                    "model": (device.model if device else None) or descriptor.model,
                    "application_id": descriptor.application_id,
                    "device_id": device.id if device else None,
                    "connection": connection,
                    "support": support,
                    "last_uplink": state.uplink.received_at.isoformat()
                    if state.uplink
                    else None,
                    "last_join": state.join.received_at.isoformat()
                    if state.join
                    else None,
                    "last_status": status.received_at.isoformat() if status else None,
                    "receptions": [
                        {
                            "gateway_id": reception.gateway_id,
                            "rssi": reception.rssi,
                            "snr": reception.snr,
                        }
                        for reception in state.uplink.receptions
                    ]
                    if state.uplink
                    else [],
                    "battery_level": status.battery_level
                    if status
                    and not status.battery_level_unavailable
                    and not status.external_power_source
                    else None,
                    "external_power_source": status.external_power_source
                    if status
                    else None,
                    "downlink_margin": status.margin if status else None,
                }
            )
    return {"devices": devices, "connections": connections}


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "lorawan/devices/list"})
@callback
def websocket_list_devices(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """List devices across all LoRaWAN connections."""
    connection.send_result(msg["id"], _snapshot(hass))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {probatio.Required("type"): "lorawan/devices/subscribe"}
)
@callback
def websocket_subscribe_devices(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Send the current devices and subsequent changes."""

    device_registry = dr.async_get(hass)
    registry = hass.data[DATA_REGISTRY]
    lorawan_domains = registry.integrations.keys()
    linked_device_ids: set[str] = set()

    @callback
    def send_snapshot() -> None:
        snapshot = _snapshot(hass)
        linked_device_ids.clear()
        linked_device_ids.update(
            device["device_id"]
            for device in snapshot["devices"]
            if device["device_id"] is not None
        )
        connection.send_event(msg["id"], snapshot)

    debouncer = Debouncer(
        hass, _LOGGER, cooldown=1, immediate=False, function=send_snapshot
    )

    @callback
    def registry_updated(event: Event[dr.EventDeviceRegistryUpdatedData]) -> None:
        device_id = event.data["device_id"]
        if device_id in linked_device_ids:
            debouncer.async_schedule_call()
            return
        if (device := device_registry.async_get(device_id)) is None:
            return
        entry = hass.config_entries.async_get_entry(device.config_entry_id)
        if entry is not None and entry.domain in lorawan_domains:
            debouncer.async_schedule_call()

    @callback
    def entry_changed(_change: ConfigEntryChange, entry: ConfigEntry) -> None:
        if entry.entry_id in registry.connections or entry.domain in lorawan_domains:
            debouncer.async_schedule_call()

    unsubscribe_entries = async_dispatcher_connect(
        hass, SIGNAL_CONFIG_ENTRY_CHANGED, entry_changed
    )
    unsubscribe_changes = async_dispatcher_connect(
        hass, SIGNAL_DEVICES_CHANGED, debouncer.async_schedule_call
    )
    unsubscribe_registry = hass.bus.async_listen(
        dr.EVENT_DEVICE_REGISTRY_UPDATED, registry_updated
    )

    @callback
    def unsubscribe() -> None:
        unsubscribe_changes()
        unsubscribe_registry()
        unsubscribe_entries()
        debouncer.async_shutdown()

    connection.subscriptions[msg["id"]] = unsubscribe
    connection.send_result(msg["id"])
    send_snapshot()
