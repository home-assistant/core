"""Diagnostics support for Hikvision."""

from dataclasses import asdict
import math
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
from homeassistant.exceptions import HomeAssistantError

from . import HikvisionConfigEntry
from .coordinator import (
    HikvisionDeviceCoordinator,
    HikvisionImageCoordinator,
    detection_path,
)

TO_REDACT = {CONF_HOST, CONF_PASSWORD, CONF_USERNAME, "title", "unique_id"}

# The camera's own documents, as it sends them: they hold image settings only,
# and are what is needed to report a camera model or add it to pyhik's tests.
RAW_DOCUMENTS = ("capabilities", "values")


def _raw_endpoints(channel: int | None) -> dict[str, str]:
    """Return where each document is read: the camera's, or the NVR's proxy."""
    if channel is None:
        endpoint = ENDPOINT_IMAGE_CHANNEL.format(channel=1)
    else:
        endpoint = ENDPOINT_IMAGE_PROXY_CHANNEL.format(channel=channel)
    return {"capabilities": f"{endpoint}/capabilities", "values": endpoint}


def _read_raw_document(client: ISAPIClient, endpoint: str) -> str:
    """Read one of the camera's image documents, without parsing it.

    Raises ISAPIAuthError on a 401, so that the coordinator deals with the rejected
    password.
    """
    try:
        response = client.request_raw("GET", endpoint)
    except ISAPIError as err:
        # The text of the error can hold the address of the camera, which is not
        # redacted here, so only the kind of error is reported.
        return f"error: {type(err).__name__}"
    if response.status_code == 401:
        raise ISAPIAuthError("The device rejected the credentials", 401)
    return response.text if response.ok else f"error: HTTP {response.status_code}"


def _bound(value: float | None) -> float | str | None:
    """Return an end of a range as JSON can hold it.

    pyHik parses "nan" and "inf" from the camera as floats, which JSON cannot hold:
    strict parsers reject the NaN and Infinity tokens. They are kept as text, as the
    camera's odd range is what is worth reporting.
    """
    return value if value is None or math.isfinite(value) else str(value)


def _setting_to_dict(
    setting: ImageSetting, values: dict[str, str], known_paths: set[str]
) -> dict[str, Any]:
    """Describe a discovered image setting and its current value.

    values is keyed by the lowercase path: the camera may spell a path in its
    values otherwise than in its capabilities.
    """
    return {
        "type": setting.type.value,
        "options": setting.options,
        "min": _bound(setting.min_value),
        "max": _bound(setting.max_value),
        "value": values.get(setting.path.lower()),
        "linked_enabled_path": setting.linked_enabled_path,
        "off_value": setting.off_value,
        # Whether this integration has an entity for the setting. Settings it
        # does not know are the ones worth reporting.
        "known": setting.path.lower() in known_paths,
    }


async def _async_read_raw_documents(
    coordinator: HikvisionImageCoordinator,
) -> dict[str, str]:
    """Read the raw documents as the coordinator sends any request.

    One request each: the event stream can have the password rejected while the
    first is sent, and the next one is then not sent with it.
    """
    documents: dict[str, str] = {}
    for name, endpoint in _raw_endpoints(coordinator.channel).items():
        try:
            documents[name] = await coordinator.async_diagnostics_request(
                _read_raw_document, coordinator.client, endpoint
            )
        except ISAPIAuthError:
            reason = "HTTP 401"
        except HomeAssistantError:
            reason = (
                "credentials rejected"
                if coordinator.credentials_rejected
                else "the image settings client is closing"
            )
        else:
            continue
        return {**dict.fromkeys(RAW_DOCUMENTS, f"error: {reason}"), **documents}
    return documents


async def _async_read_values(
    coordinator: HikvisionImageCoordinator,
) -> tuple[dict[str, str], str]:
    """Return the current values and where they come from.

    The cached values are used if the camera cannot be read: they are the last ones
    a poll or a write got.
    """
    try:
        return await coordinator.async_read_values(), "camera"
    except ISAPIError, HomeAssistantError:
        return coordinator.data or {}, "cached"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HikvisionConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diagnostics: dict[str, Any] = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "pyhik_version": pyhik.__version__,
        "device_type": None,
        "channels": [],
        "image_settings": None,
    }
    # An entry whose setup failed before it got its runtime data, or one that was
    # unloaded, has none: the entry and the library version are still worth having.
    if (data := getattr(entry, "runtime_data", None)) is None:
        return diagnostics
    diagnostics["device_type"] = data.device_type
    diagnostics["channels"] = sorted(data.channels)

    for coordinator in data.image_coordinators:
        if isinstance(coordinator, HikvisionDeviceCoordinator):
            # The device's own controls, as the last poll found them.
            diagnostics["device_controls"] = {
                "outputs": [asdict(port) for port in coordinator.outputs or ()],
                "inputs": [asdict(port) for port in coordinator.inputs or ()],
                "input_states": [
                    asdict(port) for port in coordinator.input_states or ()
                ],
                "holidays": [
                    # Their names are the user's own.
                    async_redact_data(asdict(holiday), {"name"})
                    for holiday in coordinator.holidays.values()
                ],
                "values": dict(coordinator.data or {}),
            }
            continue
        description = await _async_describe(coordinator)
        if coordinator.channel is None:
            diagnostics["image_settings"] = description
        else:
            # The cameras attached to an NVR, by channel ID.
            diagnostics.setdefault("channel_image_settings", {})[
                str(coordinator.channel)
            ] = description

    return diagnostics


async def _async_describe(coordinator: HikvisionImageCoordinator) -> dict[str, Any]:
    """Describe the image settings of one camera."""
    values, values_source = await _async_read_values(coordinator)
    # The flag of a linked mode is part of its setting: pyHik folds it in.
    discovered = {
        path.lower()
        for setting in coordinator.settings
        for path in (setting.path, setting.linked_enabled_path)
        if path is not None
    }
    values_by_path = {path.lower(): value for path, value in values.items()}
    detections = {
        detection_path(detection): detection
        for detection in coordinator.detections or ()
    }
    return {
        "values_source": values_source,
        "settings": {
            setting.path: _setting_to_dict(
                setting,
                values_by_path,
                coordinator.entity_paths,
            )
            for setting in coordinator.settings
        },
        # Values the camera reports that no discovered setting describes.
        "other_values": {
            path: value
            for path, value in values.items()
            if path.lower() not in discovered and path not in detections
        },
        # The detections the camera has, as the last poll found them: on, off, or
        # None if it could not read them.
        "detections": {
            detection: (coordinator.data or {}).get(path)
            for path, detection in detections.items()
        },
        "raw_documents": await _async_read_raw_documents(coordinator),
    }
