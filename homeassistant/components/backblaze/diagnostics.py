"""Diagnostics support for Backblaze."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import BackblazeConfigEntry
from .const import CONF_APPLICATION_KEY, CONF_KEY_ID

TO_REDACT = {CONF_APPLICATION_KEY, CONF_KEY_ID}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BackblazeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    bucket = entry.runtime_data

    # Get bucket information (safely)
    try:
        bucket_info = {
            "name": bucket.name,
            "id": bucket.id_,
            "type": getattr(bucket, "type_", "unknown"),
            "cors_rules": getattr(bucket, "cors_rules", "not_available"),
            "lifecycle_rules": getattr(bucket, "lifecycle_rules", "not_available"),
            "revision": getattr(bucket, "revision", "not_available"),
        }
    except (AttributeError, TypeError, ValueError):
        bucket_info = {"error": "Failed to retrieve bucket information"}

    # Get account information (safely)
    try:
        account_info = bucket.api.account_info
        account_data: dict[str, Any] = {
            "account_id": getattr(
                account_info, "get_account_id", lambda: "not_available"
            )(),
            "api_url": getattr(account_info, "get_api_url", lambda: "not_available")(),
            "download_url": getattr(
                account_info, "get_download_url", lambda: "not_available"
            )(),
            "minimum_part_size": getattr(
                account_info, "get_minimum_part_size", lambda: "not_available"
            )(),
            "allowed": getattr(account_info, "get_allowed", dict)(),
        }

        # Redact sensitive information from allowed capabilities
        if (
            isinstance(account_data["allowed"], dict)
            and "bucketId" in account_data["allowed"]
        ):
            account_data["allowed"] = async_redact_data(
                account_data["allowed"], {"bucketId", "bucketName", "namePrefix"}
            )
    except (AttributeError, TypeError, ValueError):
        account_data = {"error": "Failed to retrieve account information"}

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "entry_options": entry.options,
        "bucket_info": bucket_info,
        "account_info": account_data,
    }
