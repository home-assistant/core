"""Utility functions for the Span integration."""

import logging

from span_panel_api import SpanBatterySnapshot, SpanEvseSnapshot, SpanPanelSnapshot

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def snapshot_to_device_info(
    snapshot: SpanPanelSnapshot,
    device_name: str | None = None,
    host: str | None = None,
) -> DeviceInfo:
    """Convert a SpanPanelSnapshot to a Home Assistant device info object."""
    configuration_url = f"http://{host}" if host else None

    return DeviceInfo(
        identifiers={(DOMAIN, snapshot.serial_number)},
        manufacturer="Span",
        model="SPAN Panel",
        name=device_name or "Span Panel",
        sw_version=snapshot.firmware_version,
        configuration_url=configuration_url,
    )


def bess_device_info(
    panel_identifier: str,
    battery: SpanBatterySnapshot,
    panel_name: str,
) -> DeviceInfo:
    """Create DeviceInfo for a BESS sub-device linked to the parent panel."""
    name = f"{panel_name} Battery"
    return DeviceInfo(
        identifiers={(DOMAIN, f"{panel_identifier}_bess")},
        name=name,
        manufacturer=battery.vendor_name or "Unknown",
        model=battery.product_name or "Battery Storage",
        serial_number=battery.serial_number,
        sw_version=battery.software_version,
        via_device=(DOMAIN, panel_identifier),
    )


def evse_device_info(
    panel_identifier: str,
    evse: SpanEvseSnapshot,
    panel_name: str,
    display_suffix: str | None = None,
) -> DeviceInfo:
    """Create DeviceInfo for an EVSE sub-device linked to the parent panel."""
    base_name = evse.product_name or "EV Charger"
    name = f"{base_name} ({display_suffix})" if display_suffix else base_name
    name = f"{panel_name} {name}"
    return DeviceInfo(
        identifiers={(DOMAIN, f"{panel_identifier}_evse_{evse.node_id}")},
        name=name,
        manufacturer=evse.vendor_name or "SPAN",
        model=evse.product_name or "SPAN Drive",
        serial_number=evse.serial_number,
        sw_version=evse.software_version,
        via_device=(DOMAIN, panel_identifier),
    )
