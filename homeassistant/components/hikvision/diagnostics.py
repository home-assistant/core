"""Diagnostics support for Hikvision."""

from typing import Any

import pyhik
from pyhik.image import ImageSetting
from pyhik.isapi import (
    ENDPOINT_IMAGE_CHANNEL,
    ENDPOINT_IMAGE_PROXY_CHANNEL,
    ISAPIClient,
    ISAPIError,
)

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import HikvisionConfigEntry
from .coordinator import HikvisionImageCoordinator

TO_REDACT = {CONF_HOST, CONF_PASSWORD, CONF_USERNAME, "title", "unique_id"}


def _read_raw_documents(client: ISAPIClient, channel: int | None) -> dict[str, str]:
    """Read the image documents as the device sends them, without parsing.

    They hold image settings only, and are what is needed to report a camera model
    or add it to pyhik's tests.
    """
    if channel is None:
        endpoint = ENDPOINT_IMAGE_CHANNEL.format(channel=1)
    else:
        endpoint = ENDPOINT_IMAGE_PROXY_CHANNEL.format(channel=channel)
    documents: dict[str, str] = {}
    for name, path in (
        ("capabilities", f"{endpoint}/capabilities"),
        ("values", endpoint),
    ):
        try:
            response = client.request_raw("GET", path)
        except ISAPIError as err:
            # The text of the error can hold the address of the camera, which is not
            # redacted here, so only the kind of error is reported.
            documents[name] = f"error: {type(err).__name__}"
            continue
        documents[name] = (
            response.text if response.ok else f"error: HTTP {response.status_code}"
        )
        if response.status_code == 401:
            # Do not send the rejected password again for the next document.
            for other in ("capabilities", "values"):
                documents.setdefault(other, documents[name])
            break
    return documents


def _setting_to_dict(
    setting: ImageSetting, values: dict[str, str], known_paths: set[str]
) -> dict[str, Any]:
    """Describe a discovered image setting and its current value."""
    return {
        "type": setting.type.value,
        "options": setting.options,
        "min": setting.min_value,
        "max": setting.max_value,
        "value": values.get(setting.path),
        "linked_enabled_path": setting.linked_enabled_path,
        "off_value": setting.off_value,
        # Whether this integration has an entity for the setting. Settings it
        # does not know are the ones worth reporting.
        "known": setting.path.lower() in known_paths,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HikvisionConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    diagnostics: dict[str, Any] = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "pyhik_version": pyhik.__version__,
        "device_type": data.device_type,
        "channels": sorted(data.channels),
        "image_settings": None,
    }

    for coordinator in data.image_coordinators:
        description = await _async_describe(hass, entry, coordinator)
        if coordinator.channel is None:
            diagnostics["image_settings"] = description
        else:
            # The cameras attached to an NVR, by channel ID.
            diagnostics.setdefault("channel_image_settings", {})[
                str(coordinator.channel)
            ] = description

    return diagnostics


async def _async_describe(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    coordinator: HikvisionImageCoordinator,
) -> dict[str, Any]:
    """Describe the image settings of one camera."""
    values = coordinator.data or {}
    discovered = {setting.path for setting in coordinator.settings}
    async with coordinator.lock:
        if entry.runtime_data.image_credentials_rejected:
            # Asking again would send the rejected password to the device once more.
            raw_documents = dict.fromkeys(
                ("capabilities", "values"), "error: credentials rejected"
            )
        else:
            raw_documents = await hass.async_add_executor_job(
                _read_raw_documents, coordinator.client, coordinator.channel
            )
    return {
        "settings": {
            setting.path: _setting_to_dict(setting, values, coordinator.entity_paths)
            for setting in coordinator.settings
        },
        # Values the camera reports that no discovered setting describes.
        "other_values": {
            path: value for path, value in values.items() if path not in discovered
        },
        "raw_documents": raw_documents,
    }
