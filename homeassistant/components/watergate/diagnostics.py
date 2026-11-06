"""Diagnostics support for Watergate."""

from typing import Any

from watergate_local_api.models import (
    AutoShutOffState,
    DeviceStateV2,
    NetworkingData,
    TelemetryData,
)
from watergate_local_api.models.water_meter import WaterMeter

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_IP_ADDRESS, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant

from .coordinator import WatergateConfigEntry

# The webhook id is the only secret protecting the webhook endpoint. The address,
# gateway, subnet and SSID locate the user's network, and the serial number
# identifies the device (it is also the config entry's unique id).
TO_REDACT = {
    CONF_IP_ADDRESS,
    CONF_WEBHOOK_ID,
    "unique_id",
    "serial_number",
    "ip",
    "gateway",
    "subnet",
    "ssid",
}


def _water_meter(meter: WaterMeter | None) -> dict[str, Any] | None:
    """Return a water meter as a dict."""
    return {"volume": meter.volume, "duration": meter.duration} if meter else None


def _device_state(state: DeviceStateV2 | None) -> dict[str, Any] | None:
    """Return the device state as a dict.

    A device without device state v2 may report no state at all.
    """
    if state is None:
        return None
    return {
        "valve_state": state.valve_state,
        "water_flow_indicator": state.water_flow_indicator,
        "mqtt_status": state.mqtt_status,
        "wifi_status": state.wifi_status,
        "power_supply": state.power_supply,
        "firmware_version": state.firmware_version,
        "uptime": state.uptime,
        "water_meter_positive": _water_meter(state.water_meter_positive),
        "water_meter_negative": _water_meter(state.water_meter_negative),
        "serial_number": state.serial_number,
    }


def _telemetry(telemetry: TelemetryData) -> dict[str, Any]:
    """Return the telemetry as a dict."""
    event = telemetry.ongoing_event
    return {
        "flow": telemetry.flow,
        "pressure": telemetry.pressure,
        "water_temperature": telemetry.water_temperature,
        "ongoing_event": (
            {"volume": event.volume, "duration": event.duration} if event else None
        ),
        "errors": telemetry.errors,
    }


def _networking(networking: NetworkingData) -> dict[str, Any]:
    """Return the networking data as a dict."""
    return {
        "mqtt_connected": networking.mqtt_connected,
        "wifi_connected": networking.wifi_connected,
        "ip": networking.ip,
        "gateway": networking.gateway,
        "subnet": networking.subnet,
        "ssid": networking.ssid,
        "rssi": networking.rssi,
        "wifi_uptime": networking.wifi_uptime,
        "mqtt_uptime": networking.mqtt_uptime,
    }


def _auto_shut_off(auto_shut_off: AutoShutOffState) -> dict[str, Any]:
    """Return the auto shut-off state as a dict."""
    return {
        "enabled": auto_shut_off.enabled,
        "volume_threshold": auto_shut_off.volume_threshold,
        "duration_threshold": auto_shut_off.duration_threshold,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WatergateConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data

    return {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        # Without data the first refresh has not succeeded (the entry is retrying setup).
        "data": (
            async_redact_data(
                {
                    "state": _device_state(data.state),
                    "telemetry": _telemetry(data.telemetry),
                    "networking": _networking(data.networking),
                    "auto_shut_off": _auto_shut_off(data.auto_shut_off),
                },
                TO_REDACT,
            )
            if data
            else None
        ),
    }
