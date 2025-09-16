"""Repair issues for the Backblaze integration."""

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

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ISSUE_BUCKET_ACCESS_RESTRICTED = "bucket_access_restricted"
ISSUE_BUCKET_NOT_FOUND = "bucket_not_found"


async def async_check_for_repair_issues(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Check for common issues that require user action."""
    bucket = entry.runtime_data

    try:
        # Test basic connectivity and permissions
        await hass.async_add_executor_job(bucket.api.account_info.get_allowed)
    except Unauthorized:
        # Authentication failures are handled via reauth flow in setup
        pass
    except RestrictedBucket as err:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"{ISSUE_BUCKET_ACCESS_RESTRICTED}_{entry.entry_id}",
            is_fixable=True,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.ERROR,
            translation_key=ISSUE_BUCKET_ACCESS_RESTRICTED,
            translation_placeholders={
                "title": entry.title,
                "bucket_name": err.bucket_name,
                "entry_id": entry.entry_id,
            },
        )
    except NonExistentBucket:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"{ISSUE_BUCKET_NOT_FOUND}_{entry.entry_id}",
            is_fixable=True,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.ERROR,
            translation_key=ISSUE_BUCKET_NOT_FOUND,
            translation_placeholders={
                "title": entry.title,
                "bucket_name": entry.data.get("bucket", "unknown"),
                "entry_id": entry.entry_id,
            },
        )
    except B2Error as err:
        _LOGGER.debug("B2 connectivity test failed: %s", err)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> ConfirmRepairFlow:
    """Create a fix flow for Backblaze issues."""
    return ConfirmRepairFlow()
