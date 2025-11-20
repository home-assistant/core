"""The Home Assistant Labs integration.

This integration provides preview features that can be toggled on/off by users.
Integrations can register lab preview features in their manifest.json which will appear
in the Home Assistant Labs UI for users to enable or disable.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.backup import async_get_manager
from homeassistant.core import HomeAssistant, callback
from homeassistant.generated.labs import LABS_PREVIEW_FEATURES
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_custom_components

from .const import (
    DOMAIN,
    EVENT_LABS_UPDATED,
    LABS_DATA,
    STORAGE_KEY,
    STORAGE_VERSION,
    EventLabsUpdatedData,
    LabPreviewFeature,
    LabsData,
    LabsStoreData,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

__all__ = [
    "EVENT_LABS_UPDATED",
    "EventLabsUpdatedData",
    "async_is_preview_feature_enabled",
]


class LabsStorage(Store[LabsStoreData]):
    """Custom Store for Labs that converts between runtime and storage formats.

    Runtime format: {"preview_feature_status": {(domain, preview_feature)}}
    Storage format: {"preview_feature_status": [{"domain": str, "preview_feature": str}]}

    Only enabled features are saved to storage - if stored, it's enabled.
    """

    async def _async_load_data(self) -> LabsStoreData | None:
        """Load data and convert from storage format to runtime format."""
        raw_data = await super()._async_load_data()
        if raw_data is None:
            return None

        status_list = raw_data.get("preview_feature_status", [])

        # Convert list of objects to runtime set - if stored, it's enabled
        return {
            "preview_feature_status": {
                (item["domain"], item["preview_feature"]) for item in status_list
            }
        }

    def _write_data(self, path: str, data: dict) -> None:
        """Convert from runtime format to storage format and write.

        Only saves enabled features - disabled is the default.
        """
        # Extract the actual data (has version/key wrapper)
        actual_data = data.get("data", data)

        # Check if this is Labs data (has preview_feature_status key)
        if "preview_feature_status" not in actual_data:
            # Not Labs data, write as-is
            super()._write_data(path, data)
            return

        preview_status = actual_data["preview_feature_status"]

        # Convert from runtime format (set of tuples) to storage format (list of dicts)
        status_list = [
            {"domain": domain, "preview_feature": preview_feature}
            for domain, preview_feature in preview_status
        ]

        # Build the final data structure with converted format
        data_copy = data.copy()
        data_copy["data"] = {"preview_feature_status": status_list}

        super()._write_data(path, data_copy)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Labs component."""
    store = LabsStorage(hass, STORAGE_VERSION, STORAGE_KEY, private=True)
    data = await store.async_load()

    if data is None:
        data = {"preview_feature_status": set()}

    # Scan ALL integrations for lab preview features (loaded or not)
    lab_preview_features = await _async_scan_all_preview_features(hass)

    # Clean up preview features that no longer exist
    if lab_preview_features:
        valid_keys = {
            (pf.domain, pf.preview_feature) for pf in lab_preview_features.values()
        }
        stale_keys = data["preview_feature_status"] - valid_keys

        if stale_keys:
            _LOGGER.debug(
                "Removing %d stale preview features: %s",
                len(stale_keys),
                stale_keys,
            )
            data["preview_feature_status"] -= stale_keys

            await store.async_save(data)

    hass.data[LABS_DATA] = LabsData(
        store=store,
        data=data,
        preview_features=lab_preview_features,
    )

    websocket_api.async_register_command(hass, websocket_list_preview_features)
    websocket_api.async_register_command(hass, websocket_update_preview_feature)

    return True


def _populate_preview_features(
    preview_features: dict[str, LabPreviewFeature],
    domain: str,
    labs_preview_features: dict[str, dict[str, str]],
    is_built_in: bool = True,
) -> None:
    """Populate preview features dictionary from integration preview_features.

    Args:
        preview_features: Dictionary to populate
        domain: Integration domain
        labs_preview_features: Dictionary of preview feature definitions from manifest
        is_built_in: Whether this is a built-in integration
    """
    for preview_feature_key, preview_feature_data in labs_preview_features.items():
        preview_feature = LabPreviewFeature(
            domain=domain,
            preview_feature=preview_feature_key,
            is_built_in=is_built_in,
            feedback_url=preview_feature_data.get("feedback_url"),
            learn_more_url=preview_feature_data.get("learn_more_url"),
            report_issue_url=preview_feature_data.get("report_issue_url"),
        )
        preview_features[preview_feature.full_key] = preview_feature


async def _async_scan_all_preview_features(
    hass: HomeAssistant,
) -> dict[str, LabPreviewFeature]:
    """Scan ALL available integrations for lab preview features (loaded or not)."""
    preview_features: dict[str, LabPreviewFeature] = {}

    # Load pre-generated built-in lab preview features (already includes all data)
    for domain, domain_preview_features in LABS_PREVIEW_FEATURES.items():
        _populate_preview_features(
            preview_features, domain, domain_preview_features, is_built_in=True
        )

    # Scan custom components
    custom_integrations = await async_get_custom_components(hass)
    _LOGGER.debug(
        "Loaded %d built-in + scanning %d custom integrations for lab preview features",
        len(preview_features),
        len(custom_integrations),
    )

    for integration in custom_integrations.values():
        if labs_preview_features := integration.preview_features:
            _populate_preview_features(
                preview_features,
                integration.domain,
                labs_preview_features,
                is_built_in=False,
            )

    _LOGGER.debug("Loaded %d total lab preview features", len(preview_features))
    return preview_features


@callback
def async_is_preview_feature_enabled(
    hass: HomeAssistant, domain: str, preview_feature: str
) -> bool:
    """Check if a lab preview feature is enabled.

    Args:
        hass: HomeAssistant instance
        domain: Integration domain
        preview_feature: Preview feature name

    Returns:
        True if the preview feature is enabled, False otherwise
    """
    if LABS_DATA not in hass.data:
        return False

    labs_data = hass.data[LABS_DATA]
    return (domain, preview_feature) in labs_data.data["preview_feature_status"]


@callback
@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "labs/list"})
def websocket_list_preview_features(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List all lab preview features filtered by loaded integrations."""
    labs_data = hass.data[LABS_DATA]
    loaded_components = hass.config.components

    preview_features: list[dict[str, Any]] = [
        preview_feature.to_dict(
            (preview_feature.domain, preview_feature.preview_feature)
            in labs_data.data["preview_feature_status"]
        )
        for preview_feature_key, preview_feature in labs_data.preview_features.items()
        if preview_feature.domain in loaded_components
    ]

    connection.send_result(msg["id"], {"features": preview_features})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "labs/update",
        vol.Required("domain"): str,
        vol.Required("preview_feature"): str,
        vol.Required("enabled"): bool,
        vol.Optional("create_backup", default=False): bool,
    }
)
@websocket_api.async_response
async def websocket_update_preview_feature(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update a lab preview feature state."""
    domain = msg["domain"]
    preview_feature = msg["preview_feature"]
    enabled = msg["enabled"]
    create_backup = msg["create_backup"]

    labs_data = hass.data[LABS_DATA]

    # Build preview_feature_id for lookup
    preview_feature_id = f"{domain}.{preview_feature}"

    # Validate preview feature exists
    if preview_feature_id not in labs_data.preview_features:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            f"Preview feature {preview_feature_id} not found",
        )
        return

    # Create backup if requested and enabling
    if create_backup and enabled:
        try:
            backup_manager = async_get_manager(hass)
            await backup_manager.async_create_automatic_backup()
        except Exception as err:  # noqa: BLE001 - websocket handlers can catch broad exceptions
            connection.send_error(
                msg["id"],
                websocket_api.ERR_UNKNOWN_ERROR,
                f"Error creating backup: {err}",
            )
            return

    # Update storage (only store enabled features, remove if disabled)
    if enabled:
        labs_data.data["preview_feature_status"].add((domain, preview_feature))
    else:
        labs_data.data["preview_feature_status"].discard((domain, preview_feature))

    # Save changes immediately
    await labs_data.store.async_save(labs_data.data)

    # Fire event
    event_data: EventLabsUpdatedData = {
        "domain": domain,
        "preview_feature": preview_feature,
        "enabled": enabled,
    }
    hass.bus.async_fire(EVENT_LABS_UPDATED, event_data)

    connection.send_result(msg["id"])
