"""Diagnostics support for Backblaze B2."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import BackblazeConfigEntry
from .const import CONF_APPLICATION_KEY, CONF_KEY_ID

TO_REDACT_ENTRY_DATA = {CONF_APPLICATION_KEY, CONF_KEY_ID}
TO_REDACT_ACCOUNT_DATA_ALLOWED = {"bucketId", "bucketName", "namePrefix"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BackblazeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    bucket = entry.runtime_data

    try:
        bucket_info = {
            "name": bucket.name,
            "id": bucket.id_,
            "type": bucket.type_,
            "cors_rules": bucket.cors_rules,
            "lifecycle_rules": bucket.lifecycle_rules,
            "revision": bucket.revision,
        }

        account_info = bucket.api.account_info
        account_data: dict[str, Any] = {
            "account_id": account_info.get_account_id(),
            "api_url": account_info.get_api_url(),
            "download_url": account_info.get_download_url(),
            "minimum_part_size": account_info.get_minimum_part_size(),
            "allowed": account_info.get_allowed(),
        }

        if isinstance(account_data["allowed"], dict):
            account_data["allowed"] = async_redact_data(
                account_data["allowed"], TO_REDACT_ACCOUNT_DATA_ALLOWED
            )

    except (AttributeError, TypeError, ValueError, KeyError):
        bucket_info = {"name": "unknown", "id": "unknown"}
        account_data = {"error": "Failed to retrieve detailed account information"}

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT_ENTRY_DATA),
        "entry_options": entry.options,
        "bucket_info": bucket_info,
        "account_info": account_data,
    }
