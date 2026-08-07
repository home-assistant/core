"""Helper functions for LG webOS TV."""

from aiowebostv import WebOsTvState

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN, LIVE_TV_APP_ID


@callback
def async_get_device_entry_by_device_id(
    hass: HomeAssistant, device_id: str
) -> DeviceEntry:
    """Get Device Entry from Device Registry by device ID.

    Raises ValueError if device ID is invalid.
    """
    device_reg = dr.async_get(hass)
    if (device := device_reg.async_get(device_id)) is None:
        raise ValueError(f"Device {device_id} is not a valid {DOMAIN} device.")

    return device


def get_sources(tv_state: WebOsTvState) -> list[str]:
    """Construct sources list."""
    sources = []
    found_live_tv = False
    for app in tv_state.apps.values():
        sources.append(app["title"])
        if app["id"] == LIVE_TV_APP_ID:
            found_live_tv = True

    for source in tv_state.inputs.values():
        sources.append(source["label"])
        if source["appId"] == LIVE_TV_APP_ID:
            found_live_tv = True

    if not found_live_tv:
        sources.append("Live TV")

    # Preserve order when filtering duplicates
    return list(dict.fromkeys(sources))
