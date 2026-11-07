"""Helper functions for LG webOS TV."""

from collections.abc import Mapping

from aiowebostv import WebOsTvState
from wakeonlan import create_magic_packet

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN, LIVE_TV_APP_ID


def get_mac_addresses(connection_info: Mapping[str, object]) -> dict[str, str]:
    """Return valid MAC addresses reported for the TV's network interfaces."""
    macs = {}
    for interface in ("wiredInfo", "wifiInfo"):
        if not isinstance(info := connection_info.get(interface), Mapping):
            continue
        if not isinstance(mac := info.get("macAddress"), str) or not mac:
            continue
        try:
            create_magic_packet(mac)
        except ValueError:
            continue
        macs[interface] = dr.format_mac(mac)
    return macs


@callback
def async_get_device_entry_by_device_id(
    hass: HomeAssistant, device_id: str
) -> DeviceEntry:
    """Get Device Entry from Device Registry by device ID.

    Raises ValueError if device ID is invalid.
    """
    device_reg = dr.async_get(hass)
    if (device := device_reg.async_get(device_id, include_child_devices=False)) is None:
        raise ValueError(f"Device {device_id} is not a valid {DOMAIN} device.")

    return device


@callback
def async_get_device_id_from_entity_id(hass: HomeAssistant, entity_id: str) -> str:
    """Get device ID from an entity ID.

    Raises HomeAssistantError if entity or device ID is invalid.
    """
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(entity_id)

    if (
        entity_entry is None
        or entity_entry.device_id is None
        or entity_entry.platform != DOMAIN
    ):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_entity_id",
            translation_placeholders={"entity_id": entity_id},
        )

    return entity_entry.device_id


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
