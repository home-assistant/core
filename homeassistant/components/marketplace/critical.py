"""Repositories the catalog marks as critical, and the repairs explaining them."""

from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .utils.storage import async_load_from_storage, async_save_to_storage

CRITICAL_ISSUE_PREFIX = "critical_repository_"


@callback
def async_create_critical_repository_issue(
    hass: HomeAssistant, critical: dict[str, Any]
) -> None:
    """Explain a repository that was removed because the catalog marks it critical."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{CRITICAL_ISSUE_PREFIX}{critical['repository']}",
        # Home Assistant restarts right after the removal
        is_persistent=True,
        is_fixable=True,
        severity=ir.IssueSeverity.CRITICAL,
        learn_more_url=critical["link"],
        translation_key="critical_repository",
        translation_placeholders={
            "repository": critical["repository"],
            "reason": critical["reason"],
        },
        data={"repository": critical["repository"], "reason": critical["reason"]},
    )


async def async_acknowledge_critical_repository(
    hass: HomeAssistant, repository: str
) -> list[dict[str, Any]]:
    """Store that the removal of a critical repository was seen."""
    critical = await async_load_from_storage(hass, "critical") or []
    for stored in critical:
        if stored["repository"] == repository:
            stored["acknowledged"] = True
    await async_save_to_storage(hass, "critical", critical)

    ir.async_delete_issue(hass, DOMAIN, f"{CRITICAL_ISSUE_PREFIX}{repository}")
    return critical
