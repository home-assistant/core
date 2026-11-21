"""Diagnostics support for Hikvision."""

import math
from typing import Any

import pyhik
from pyhik.image import ImageSetting
from pyhik.isapi import ENDPOINT_IMAGE_CHANNEL, ISAPIAuthError, ISAPIClient, ISAPIError

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import HikvisionConfigEntry
from .coordinator import HikvisionImageCoordinator

TO_REDACT = {CONF_HOST, CONF_PASSWORD, CONF_USERNAME, "title", "unique_id"}

# The camera's own documents, as it sends them: they hold image settings only,
# and are what is needed to report a camera model or add it to pyhik's tests.
RAW_DOCUMENTS = {
    "capabilities": f"{ENDPOINT_IMAGE_CHANNEL.format(channel=1)}/capabilities",
    "values": ENDPOINT_IMAGE_CHANNEL.format(channel=1),
}


def _read_raw_documents(client: ISAPIClient, documents: dict[str, str]) -> None:
    """Read the camera's image documents into documents, without parsing them.

    Raises ISAPIAuthError on a 401, once every document has its entry, so that the
    coordinator deals with the rejected password.
    """
    for name, endpoint in RAW_DOCUMENTS.items():
        try:
            response = client.request_raw("GET", endpoint)
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
            for other in RAW_DOCUMENTS:
                documents.setdefault(other, documents[name])
            raise ISAPIAuthError("The device rejected the credentials", 401)


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
    """Read the raw documents as the coordinator sends any request."""
    documents: dict[str, str] = {}
    try:
        await coordinator.async_diagnostics_request(
            _read_raw_documents, coordinator.client, documents
        )
    except ISAPIAuthError:
        # Each document says so already.
        pass
    except HomeAssistantError:
        reason = (
            "credentials rejected"
            if coordinator.credentials_rejected
            else "the image settings client is closing"
        )
        return dict.fromkeys(RAW_DOCUMENTS, f"error: {reason}")
    return documents


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

    if (coordinator := data.image_coordinator) is not None:
        values = coordinator.data or {}
        # The flag of a linked mode is part of its setting: pyHik folds it in.
        discovered = {
            path.lower()
            for setting in coordinator.settings
            for path in (setting.path, setting.linked_enabled_path)
            if path is not None
        }
        diagnostics["image_settings"] = {
            "settings": {
                setting.path: _setting_to_dict(
                    setting,
                    {path.lower(): value for path, value in values.items()},
                    coordinator.entity_paths,
                )
                for setting in coordinator.settings
            },
            # Values the camera reports that no discovered setting describes.
            "other_values": {
                path: value
                for path, value in values.items()
                if path.lower() not in discovered
            },
            "raw_documents": await _async_read_raw_documents(coordinator),
        }

    return diagnostics
