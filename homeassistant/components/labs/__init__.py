"""The Home Assistant Labs integration.

This integration provides experimental features that can be toggled on/off by users.
Integrations can register lab features in their manifest.json which will appear
in the Home Assistant Labs UI for users to enable or disable.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.generated.labs import LABS_FEATURES
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import Integration, async_get_custom_components

from .const import (
    DOMAIN,
    EVENT_LABS_UPDATED,
    LABS_DATA,
    STORAGE_KEY,
    STORAGE_VERSION,
    LabFeature,
    LabsData,
    LabsStoreData,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

__all__ = [
    "DOMAIN",
    "EVENT_LABS_UPDATED",
    "async_is_experimental_feature_enabled",
    "async_setup",
]


async def _async_scan_all_lab_features(hass: HomeAssistant) -> dict[str, LabFeature]:
    """Scan ALL available integrations for lab features (loaded or not)."""
    features: dict[str, LabFeature] = {}

    # Load pre-generated built-in labs features
    def _load_builtin_features() -> dict[str, LabFeature]:
        """Load built-in labs features from pre-generated data."""
        from homeassistant import components  # noqa: PLC0415

        builtin_features: dict[str, LabFeature] = {}

        # Iterate through pre-generated LABS_FEATURES
        for domain, feature_ids in LABS_FEATURES.items():
            try:
                integration = Integration.resolve_from_root(hass, components, domain)
                if not integration:
                    continue

                labs_features = integration.manifest.get("labs_features", {})

                for feature_id in feature_ids:
                    if (
                        not isinstance(labs_features, dict)
                        or feature_id not in labs_features
                    ):
                        continue

                    feature_data = labs_features[feature_id]
                    if not isinstance(feature_data, dict):
                        continue

                    feature = LabFeature(
                        domain=domain,
                        feature=feature_id,
                        feedback_url=feature_data.get("feedback_url"),
                        learn_more_url=feature_data.get("learn_more_url"),
                        report_issue_url=feature_data.get("report_issue_url"),
                    )
                    builtin_features[feature.full_key] = feature

            except Exception:  # noqa: BLE001
                _LOGGER.debug("Error loading integration %s for labs features", domain)
                continue

        return builtin_features

    # Load built-in features in executor (only loads manifests for integrations with features)
    builtin_features = await hass.async_add_executor_job(_load_builtin_features)
    features.update(builtin_features)

    # Scan custom components
    custom_integrations = await async_get_custom_components(hass)
    _LOGGER.debug(
        "Loaded %d built-in + scanning %d custom integrations for lab features",
        len(builtin_features),
        len(custom_integrations),
    )

    for integration in custom_integrations.values():
        labs_features = integration.manifest.get("labs_features")
        if not labs_features or not isinstance(labs_features, dict):
            continue

        # labs_features is a dict[str, dict[str, str]]
        for feature_key, feature_data in labs_features.items():
            if not isinstance(feature_data, dict):
                continue
            feature = LabFeature(
                domain=integration.domain,
                feature=feature_key,
                feedback_url=feature_data.get("feedback_url"),
                learn_more_url=feature_data.get("learn_more_url"),
                report_issue_url=feature_data.get("report_issue_url"),
            )
            features[feature.full_key] = feature

    _LOGGER.debug("Loaded %d total lab features", len(features))
    return features


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Labs component."""
    store = Store[LabsStoreData](hass, STORAGE_VERSION, STORAGE_KEY, private=True)
    data = await store.async_load()

    if data is None:
        data = {"features": {}}

    # Scan ALL integrations for lab features (loaded or not)
    lab_features = await _async_scan_all_lab_features(hass)

    # Clean up features that no longer exist
    if lab_features:
        current_features = set(data["features"].keys())
        valid_features = set(lab_features.keys())
        stale_features = current_features - valid_features

        if stale_features:
            _LOGGER.debug(
                "Removing %d stale lab features: %s",
                len(stale_features),
                stale_features,
            )
            for feature_id in stale_features:
                del data["features"][feature_id]
            await store.async_save(data)

    hass.data[LABS_DATA] = LabsData(
        store=store,
        data=data,
        features=lab_features,
    )

    websocket_api.async_register_command(hass, websocket_list_features)
    websocket_api.async_register_command(hass, websocket_update_feature)

    return True


@callback
def async_is_experimental_feature_enabled(
    hass: HomeAssistant, domain: str, feature: str
) -> bool:
    """Check if an experimental lab feature is enabled.

    Args:
        hass: HomeAssistant instance
        domain: Integration domain
        feature: Feature name

    Returns:
        True if the feature is enabled, False otherwise
    """
    if LABS_DATA not in hass.data:
        return False

    labs_data = hass.data[LABS_DATA]
    return labs_data.data["features"].get(f"{domain}.{feature}", False)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "labs/list"})
def websocket_list_features(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List all lab features filtered by loaded integrations."""
    labs_data = hass.data[LABS_DATA]
    loaded_components = hass.config.components

    features: list[dict[str, Any]] = [
        {
            "feature": feature.feature,
            "domain": feature.domain,
            "enabled": labs_data.data["features"].get(feature_key, False),
            "feedback_url": feature.feedback_url,
            "learn_more_url": feature.learn_more_url,
            "report_issue_url": feature.report_issue_url,
        }
        for feature_key, feature in labs_data.features.items()
        if feature.domain in loaded_components
    ]

    connection.send_result(msg["id"], {"features": features})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "labs/update",
        vol.Required("feature_id"): str,
        vol.Required("enabled"): bool,
    }
)
@websocket_api.async_response
async def websocket_update_feature(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update a lab feature state."""
    feature_id = msg["feature_id"]
    enabled = msg["enabled"]

    labs_data = hass.data[LABS_DATA]

    # Validate feature exists
    if feature_id not in labs_data.features:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            f"Feature {feature_id} not found",
        )
        return

    # Update storage
    labs_data.data["features"][feature_id] = enabled
    await labs_data.store.async_save(labs_data.data)

    # Fire event
    hass.bus.async_fire(
        EVENT_LABS_UPDATED,
        {"feature_id": feature_id, "enabled": enabled},
    )

    connection.send_result(msg["id"])
