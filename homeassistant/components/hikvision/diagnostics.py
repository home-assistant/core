"""Diagnostics support for Hikvision."""

from functools import partial
from typing import Any

import pyhik
from pyhik.image import ImageSetting
from pyhik.isapi import (
    ENDPOINT_IMAGE_CHANNEL,
    ENDPOINT_IMAGE_PROXY_CHANNEL,
    ISAPIAuthError,
    ISAPIClient,
    ISAPIError,
)

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import HikvisionConfigEntry
from .coordinator import HikvisionImageCoordinator

TO_REDACT = {CONF_HOST, CONF_PASSWORD, CONF_USERNAME, "title", "unique_id"}


def _read_raw_document(client: ISAPIClient, path: str) -> str:
    """Read an image document as the device sends it, without parsing."""
    response = client.request_raw("GET", path)
    if response.status_code == 401:
        # The client returns an error status instead of raising it.
        raise ISAPIAuthError("The credentials were rejected", 401)
    return response.text if response.ok else f"error: HTTP {response.status_code}"


async def _async_read_raw_documents(
    coordinator: HikvisionImageCoordinator,
) -> dict[str, str]:
    """Read the image documents of a camera, one request after the other.

    They hold image settings only, and are what is needed to report a camera model
    or add it to pyhik's tests. Each one is a request of its own, so that the password
    is not sent again if the first one shows that it is rejected, or if the entry is
    unloaded in between.
    """
    if coordinator.channel is None:
        endpoint = ENDPOINT_IMAGE_CHANNEL.format(channel=1)
    else:
        endpoint = ENDPOINT_IMAGE_PROXY_CHANNEL.format(channel=coordinator.channel)
    documents: dict[str, str] = {}
    for name, path in (
        ("capabilities", f"{endpoint}/capabilities"),
        ("values", endpoint),
    ):
        try:
            documents[name] = await coordinator.async_request(
                partial(_read_raw_document, coordinator.client, path)
            )
        except ISAPIAuthError as err:
            if err.status_code == 401:
                # Rejected by now, or by this very request. Asking again would send
                # the password to the device once more.
                documents.update(
                    dict.fromkeys(
                        ("capabilities", "values"), "error: credentials rejected"
                    )
                    | documents
                )
                break
            documents[name] = f"error: {type(err).__name__}"
        except ISAPIError as err:
            # The text of the error can hold the address of the camera, which is not
            # redacted here, so only the kind of error is reported.
            documents[name] = f"error: {type(err).__name__}"
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
    raw_documents = await _async_read_raw_documents(coordinator)
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
