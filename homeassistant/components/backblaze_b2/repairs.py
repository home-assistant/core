"""Repair issues for the Backblaze B2 integration."""

from __future__ import annotations

import logging

from b2sdk.v2.exception import (
    B2Error,
    NonExistentBucket,
    RestrictedBucket,
    Unauthorized,
)

from homeassistant.components.repairs import ConfirmRepairFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import CONF_BUCKET, DOMAIN

_LOGGER = logging.getLogger(__name__)

ISSUE_BUCKET_ACCESS_RESTRICTED = "bucket_access_restricted"
ISSUE_BUCKET_NOT_FOUND = "bucket_not_found"


def _create_issue(
    hass: HomeAssistant,
    entry: ConfigEntry,
    issue_type: str,
    bucket_name: str,
) -> None:
    """Create a repair issue with standard parameters."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{issue_type}_{entry.entry_id}",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.ERROR,
        translation_key=issue_type,
        translation_placeholders={
            "brand_name": "Backblaze B2",
            "title": entry.title,
            "bucket_name": bucket_name,
            "entry_id": entry.entry_id,
        },
    )


def create_bucket_access_restricted_issue(
    hass: HomeAssistant, entry: ConfigEntry, bucket_name: str
) -> None:
    """Create a repair issue for restricted bucket access."""
    _create_issue(hass, entry, ISSUE_BUCKET_ACCESS_RESTRICTED, bucket_name)


def create_bucket_not_found_issue(
    hass: HomeAssistant, entry: ConfigEntry, bucket_name: str
) -> None:
    """Create a repair issue for non-existent bucket."""
    _create_issue(hass, entry, ISSUE_BUCKET_NOT_FOUND, bucket_name)


async def async_check_for_repair_issues(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Check for common issues that require user action."""
    bucket = entry.runtime_data
    restricted_issue_id = f"{ISSUE_BUCKET_ACCESS_RESTRICTED}_{entry.entry_id}"
    not_found_issue_id = f"{ISSUE_BUCKET_NOT_FOUND}_{entry.entry_id}"

    try:
        await hass.async_add_executor_job(bucket.api.account_info.get_allowed)
        ir.async_delete_issue(hass, DOMAIN, restricted_issue_id)
        ir.async_delete_issue(hass, DOMAIN, not_found_issue_id)
    except Unauthorized:
        entry.async_start_reauth(hass)
    except RestrictedBucket as err:
        _create_issue(hass, entry, ISSUE_BUCKET_ACCESS_RESTRICTED, err.bucket_name)
    except NonExistentBucket:
        _create_issue(hass, entry, ISSUE_BUCKET_NOT_FOUND, entry.data[CONF_BUCKET])
    except B2Error as err:
        _LOGGER.debug("B2 connectivity test failed: %s", err)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> ConfirmRepairFlow:
    """Create a fix flow for Backblaze B2 issues."""
    return ConfirmRepairFlow()
