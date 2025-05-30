"""Functions to generate names for devices and entities."""

from homeassistant.config_entries import ConfigEntry


def sam_device_uid(entry: ConfigEntry) -> str:
    """Return the UID for the SAM device."""
    return entry.entry_id


def system_device_uid(sam_uid: str, system_id: int) -> str:
    """Return the UID for a given system (e.g., 1) under a SAM."""
    return f"{sam_uid}-S{system_id}"


def zone_entity_uid(sam_uid: str, system_id: int, zone_id: int) -> str:
    """Return the UID for a given system and zone (e.g., 1 and 2) under a SAM."""
    return f"{sam_uid}-S{system_id}-Z{zone_id}"
