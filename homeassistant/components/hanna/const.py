"""Constants for the Hanna integration."""

from typing import TYPE_CHECKING, TypedDict

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import HannaDataCoordinator

DOMAIN = "hanna"

# This key is NOT private. It is found in the JavaScript code of the Hanna Cloud webapp at https://www.hannacloud.com
DEFAULT_ENCRYPTION_KEY = "MzJmODBmMDU0ZTAyNDFjYWM0YTVhOGQxY2ZlZTkwMDM="


class HannaRuntimeData(TypedDict):
    """Runtime data for Hanna config entries."""

    device_coordinators: dict[str, "HannaDataCoordinator"]


class HannaConfigEntry(ConfigEntry):
    """Config entry for Hanna integration with typed runtime data."""

    runtime_data: HannaRuntimeData | None
