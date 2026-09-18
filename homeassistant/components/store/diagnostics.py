"""Diagnostics support for the Community store."""

from typing import Any

from aiogithubapi import GitHubException

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .base import StoreConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: StoreConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    store = entry.runtime_data

    data: dict[str, Any] = {
        "entry": entry.as_dict(),
        "store": {
            "stage": store.stage,
            "version": store.version,
            "disabled_reason": store.system.disabled_reason,
            "new": store.status.new,
            "startup": store.status.startup,
            "categories": store.common.categories,
            "renamed_repositories": store.common.renamed_repositories,
            "archived_repositories": store.common.archived_repositories,
            "ignored_repositories": store.common.ignored_repositories,
            "lovelace_mode": store.core.lovelace_mode,
            "configuration": {},
        },
        "custom_repositories": [
            repo.data.full_name
            for repo in store.repositories.list_all
            if not store.repositories.is_default(str(repo.data.id))
        ],
        "repositories": [],
    }

    for key in (
        "appdaemon",
        "country",
        "debug",
        "python_script",
        "release_limit",
        "theme",
    ):
        data["store"]["configuration"][key] = getattr(store.configuration, key, None)

    for repository in store.repositories.list_downloaded:
        data["repositories"].append(
            {
                "data": repository.data.to_json(),
                "integration_manifest": repository.integration_manifest,
                "repository_manifest": repository.repository_manifest.to_dict(),
                "ref": repository.ref,
                "paths": {
                    "localpath": repository.localpath.replace(
                        store.core.config_path, "/config"
                    ),
                    "local": repository.content.path.local.replace(
                        store.core.config_path, "/config"
                    ),
                    "remote": repository.content.path.remote,
                },
            }
        )

    try:
        rate_limit_response = await store.githubapi.rate_limit()
        data["rate_limit"] = rate_limit_response.data.as_dict
    except GitHubException as exception:
        data["rate_limit"] = str(exception)

    return async_redact_data(data, ("token",))
