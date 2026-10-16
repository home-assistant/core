"""Expose LoRaWAN devices and observed radio metadata to administrators."""

from typing import Any

import probatio

from homeassistant.components import websocket_api
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .connection import DATA_REGISTRY
from .const import SIGNAL_DEVICES_CHANGED


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
    devices = []
    connections = []
    for entry_id, observations in registry.observed_connections.items():
        if (entry := hass.config_entries.async_get_entry(entry_id)) is None:
            continue
        connection = {
            "entry_id": entry_id,
            "domain": entry.domain,
            "title": entry.title,
            "connected": entry_id in registry.connections,
            "configuration_url": observations.configuration_url,
        }
        connections.append(connection)
        for state in observations.devices.values():
            descriptor = state.descriptor
            domains = [
                domain
                for domain, matchers in registry.integrations.items()
                if (descriptor.stack, descriptor.brand_id) in matchers
            ]
            vendor_entries = [
                vendor_entry
                for domain in domains
                for vendor_entry in hass.config_entries.async_entries(domain)
            ]
            device = next(
                (
                    device
                    for vendor_entry in vendor_entries
                    if (
                        device := device_registry.async_get_device_by_identifier(
                            (vendor_entry.domain, f"{entry_id}:{descriptor.dev_eui}"),
                            vendor_entry.entry_id,
                        )
                    )
                    is not None
                ),
                None,
            )
            if device is not None:
                support = "supported"
            elif descriptor.brand_id is None or not descriptor.model_id:
                support = "missing_identity"
            elif domains and not vendor_entries:
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

    @callback
    def send_snapshot() -> None:
        connection.send_event(msg["id"], _snapshot(hass))

    @callback
    def registry_updated(event: Event[dr.EventDeviceRegistryUpdatedData]) -> None:
        send_snapshot()

    unsubscribe_changes = async_dispatcher_connect(
        hass, SIGNAL_DEVICES_CHANGED, send_snapshot
    )
    unsubscribe_registry = hass.bus.async_listen(
        dr.EVENT_DEVICE_REGISTRY_UPDATED, registry_updated
    )

    @callback
    def unsubscribe() -> None:
        unsubscribe_changes()
        unsubscribe_registry()

    connection.subscriptions[msg["id"]] = unsubscribe
    connection.send_result(msg["id"])
    send_snapshot()
