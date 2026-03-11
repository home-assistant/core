"""Utility methods for the Lunatone integration."""

from lunatone_rest_api_client.models import InfoData

from homeassistant.core import HomeAssistant

from .const import DOMAIN


def resolve_uid(hass: HomeAssistant, info_data: InfoData) -> str:
    """Resolves a unique identifier for the device based on available API data."""
    serial_number = str(info_data.device.serial)
    entry = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, serial_number)
    if entry is None:
        if info_data.uid is not None:
            return info_data.uid.replace("-", "")
    return serial_number
