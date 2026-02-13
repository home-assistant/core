"""Utility methods for the Lunatone integration."""

from lunatone_rest_api_client.models import InfoData


def resolve_uid(info_data: InfoData) -> str:
    """Resolves a unique identifier for the device based on available API data."""
    if info_data.uid is not None:
        return info_data.uid.replace("-", "")
    return str(info_data.device.serial)
