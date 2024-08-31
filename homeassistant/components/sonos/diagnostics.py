"""Provides diagnostics for Sonos."""
from __future__ import annotations

import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DATA_SONOS, DOMAIN
from .speaker import SonosSpeaker

MEDIA_DIAGNOSTIC_ATTRIBUTES = (
    "album_name",
    "artist",
    "channel",
    "duration",
    "image_url",
    "queue_position",
    "playlist_name",
    "source_name",
    "title",
    "uri",
)
SPEAKER_DIAGNOSTIC_ATTRIBUTES = (
    "available",
    "battery_info",
    "hardware_version",
    "household_id",
    "is_coordinator",
    "model_name",
    "model_number",
    "software_version",
    "sonos_group_entities",
    "subscription_address",
    "subscriptions_failed",
    "version",
    "zone_name",
    "_group_members_missing",
    "_last_activity",
    "_last_event_cache",
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    payload: dict[str, Any] = {"current_timestamp": time.monotonic()}

    for section in ("discovered", "discovery_known"):
        payload[section] = {}
        data: set[Any] | dict[str, Any] = getattr(hass.data[DATA_SONOS], section)
        if isinstance(data, set):
            payload[section] = data
            continue
        for key, value in data.items():
            if isinstance(value, SonosSpeaker):
                payload[section][key] = await async_generate_speaker_info(hass, value)
            else:
                payload[section][key] = value
    return payload


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    uid = next(
        (identifier[1] for identifier in device.identifiers if identifier[0] == DOMAIN),
        None,
    )
    if uid is None:
        return {}

    if (speaker := hass.data[DATA_SONOS].discovered.get(uid)) is None:
        return {}

    return await async_generate_speaker_info(hass, speaker)


async def async_generate_media_info(
    hass: HomeAssistant, speaker: SonosSpeaker
) -> dict[str, Any]:
    """Generate a diagnostic payload for current media metadata."""
    payload: dict[str, Any] = {}

    for attrib in MEDIA_DIAGNOSTIC_ATTRIBUTES:
        payload[attrib] = getattr(speaker.media, attrib)

    def poll_current_track_info() -> dict[str, Any] | str:
        try:
            return speaker.soco.avTransport.GetPositionInfo(
                [("InstanceID", 0), ("Channel", "Master")],
                timeout=3,
            )
        except OSError as ex:
            return f"Error retrieving: {ex}"

    payload["current_track_poll"] = await hass.async_add_executor_job(
        poll_current_track_info
    )

    return payload


async def async_generate_speaker_info(
    hass: HomeAssistant, speaker: SonosSpeaker
) -> dict[str, Any]:
    """Generate the diagnostic payload for a specific speaker."""
    payload: dict[str, Any] = {}

    def get_contents(
        item: int | float | str | dict[str, Any],
    ) -> int | float | str | dict[str, Any]:
        if isinstance(item, (int, float, str)):
            return item
        if isinstance(item, dict):
            payload = {}
            for key, value in item.items():
                payload[key] = get_contents(value)
            return payload
        if hasattr(item, "__dict__"):
            return vars(item)
        return item

    for attrib in SPEAKER_DIAGNOSTIC_ATTRIBUTES:
        value = getattr(speaker, attrib)
        payload[attrib] = get_contents(value)

    payload["enabled_entities"] = {
        entity_id
        for entity_id, s in hass.data[DATA_SONOS].entity_id_mappings.items()
        if s is speaker
    }
    payload["media"] = await async_generate_media_info(hass, speaker)
    payload["activity_stats"] = speaker.activity_stats.report()
    payload["event_stats"] = speaker.event_stats.report()
    payload["zone_group_state_stats"] = {
        "processed": speaker.soco.zone_group_state.processed_count,
        "total_requests": speaker.soco.zone_group_state.total_requests,
    }
    return payload
