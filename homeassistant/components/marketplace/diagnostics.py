"""Diagnostics support for the Marketplace."""

from typing import Any

from aiogithubapi import GitHubException

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .base import MarketplaceConfigEntry
from .const import CONF_WARNING_ACCEPTED


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: MarketplaceConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    marketplace = entry.runtime_data
    warning_acceptances = marketplace.warning_acceptances

    data: dict[str, Any] = {
        "entry": entry.as_dict(),
        "marketplace": {
            "stage": marketplace.stage,
            "version": marketplace.version,
            "disabled_reason": marketplace.system.disabled_reason,
            "github_connected": marketplace.github_connected,
            "warning_accepted_users": len(warning_acceptances),
            "warning_last_accepted_at": (
                max(warning_acceptances.values()).isoformat()
                if warning_acceptances
                else None
            ),
            "warning_reminders_due": sum(
                marketplace.warning_reminder_due(user_id)
                for user_id in warning_acceptances
            ),
            "new": marketplace.status.new,
            "startup": marketplace.status.startup,
            "categories": marketplace.common.categories,
            "renamed_repositories": marketplace.common.renamed_repositories,
            "archived_repositories": marketplace.common.archived_repositories,
            "ignored_repositories": marketplace.common.ignored_repositories,
            "lovelace_mode": marketplace.core.lovelace_mode,
            "configuration": {},
        },
        "custom_repositories": [
            repo.data.full_name
            for repo in marketplace.repositories.list_all
            if not marketplace.repositories.is_default(str(repo.data.id))
        ],
        "repositories": [],
    }

    for key in ("debug",):
        data["marketplace"]["configuration"][key] = getattr(
            marketplace.configuration, key, None
        )

    for repository in marketplace.repositories.list_installed:
        data["repositories"].append(
            {
                "data": repository.data.to_json(),
                "integration_manifest": repository.integration_manifest,
                "repository_manifest": repository.repository_manifest.to_dict(),
                "ref": repository.ref,
                "paths": {
                    "localpath": repository.localpath.replace(
                        marketplace.core.config_path, "/config"
                    ),
                    "local": repository.content.path.local.replace(
                        marketplace.core.config_path, "/config"
                    ),
                    "remote": repository.content.path.remote,
                },
            }
        )

    if marketplace.github_connected:
        try:
            rate_limit_response = await marketplace.githubapi.rate_limit()
            data["rate_limit"] = rate_limit_response.data.as_dict
        except GitHubException as exception:
            data["rate_limit"] = str(exception)

    return async_redact_data(data, (CONF_WARNING_ACCEPTED, "token"))
