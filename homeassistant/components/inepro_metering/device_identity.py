"""Device-registry identity helpers for Inepro Metering."""

from typing import Any

from homeassistant.config_entries import ConfigEntry

from .const import CONF_SERIAL_NUMBER, DOMAIN
from .entry_data import ConfiguredMeter, build_meter_key


def normalize_serial_number(value: Any) -> str | None:
    """Return a normalized non-empty serial number."""
    if not isinstance(value, str):
        return None
    serial_number = value.strip()
    return serial_number or None


def configured_entry_serial(entry: ConfigEntry) -> str | None:
    """Return the persisted serial number for a single-meter entry when available."""
    return normalize_serial_number(entry.data.get(CONF_SERIAL_NUMBER))


def meter_device_identifier(
    entry: ConfigEntry,
    *,
    serial_number: str | None,
    fallback_key: str | None = None,
) -> tuple[str, str]:
    """Return the stable device-registry identifier for one physical meter."""
    if normalized_serial := normalize_serial_number(serial_number):
        return (DOMAIN, normalized_serial)
    return (DOMAIN, fallback_key or entry.entry_id)


def configured_meter_device_identifier(
    entry: ConfigEntry,
    meter: ConfiguredMeter,
    *,
    fallback_key: str | None = None,
) -> tuple[str, str]:
    """Return the device identifier for one configured meter."""
    return meter_device_identifier(
        entry,
        serial_number=meter.serial_number,
        fallback_key=fallback_key or build_meter_key(meter),
    )


def gateway_serial_number(entry: ConfigEntry, gateway=None) -> str | None:
    """Return the best known serial number for one TCP gateway."""
    if gateway is not None and (
        serial_number := normalize_serial_number(gateway.serial_number)
    ):
        return serial_number
    return configured_entry_serial(entry)


def gateway_device_identifier(
    entry: ConfigEntry,
    *,
    gateway=None,
) -> tuple[str, str]:
    """Return the stable device-registry identifier for one gateway device."""
    if serial_number := gateway_serial_number(entry, gateway):
        return (DOMAIN, serial_number)
    return (DOMAIN, f"{entry.entry_id}:gateway")
