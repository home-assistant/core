"""Shared helpers for the Culiplan integration."""

from datetime import UTC, date, datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import DOMAIN


def build_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return a canonical ``DeviceInfo`` for all Culiplan entities.

    All entities for one config entry share one device card so the user
    sees a single "Culiplan" device in the registry rather than one per
    entity.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Culiplan",
        manufacturer="Culiplan",
        model="Meal Planner",
        configuration_url="https://culiplan.com",
        entry_type=DeviceEntryType.SERVICE,
    )


def parse_dt(value: str) -> datetime:
    """Parse an ISO-8601 date or datetime string into a tz-aware datetime."""
    try:
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return datetime.combine(
            date.fromisoformat(value), datetime.min.time(), tzinfo=UTC
        )
