"""The Home Assistant Labs integration.

This integration provides preview features that can be toggled on/off by users.
Integrations can register lab preview features in their manifest.json which will appear
in the Home Assistant Labs UI for users to enable or disable.
"""

from __future__ import annotations

import logging

from homeassistant.const import EVENT_LABS_UPDATED
from homeassistant.core import HomeAssistant
from homeassistant.generated.labs import LABS_PREVIEW_FEATURES
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_custom_components

from .const import DOMAIN, LABS_DATA, STORAGE_KEY, STORAGE_VERSION
from .helpers import async_is_preview_feature_enabled, async_listen
from .models import (
    EventLabsUpdatedData,
    LabPreviewFeature,
    LabsData,
    LabsStoreData,
    NativeLabsStoreData,
)
from .websocket_api import async_setup as async_setup_ws_api

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

__all__ = [
    "EVENT_LABS_UPDATED",
    "EventLabsUpdatedData",
    "async_is_preview_feature_enabled",
    "async_listen",
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Labs component."""
    store: Store[NativeLabsStoreData] = Store(
        hass, STORAGE_VERSION, STORAGE_KEY, private=True
    )
    data = LabsStoreData.from_store_format(await store.async_load())

    # Scan ALL integrations for lab preview features (loaded or not)
    lab_preview_features = await _async_scan_all_preview_features(hass)

    # Clean up preview features that no longer exist
    if lab_preview_features:
        valid_keys = {
            (pf.domain, pf.preview_feature) for pf in lab_preview_features.values()
        }
        stale_keys = data.preview_feature_status - valid_keys

        if stale_keys:
            _LOGGER.debug(
                "Removing %d stale preview features: %s",
                len(stale_keys),
                stale_keys,
            )
            data.preview_feature_status -= stale_keys

            await store.async_save(data.to_store_format())

    hass.data[LABS_DATA] = LabsData(
        store=store,
        data=data,
        preview_features=lab_preview_features,
    )

    async_setup_ws_api(hass)

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
