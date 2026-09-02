"""Diagnostics support for HACS."""

from __future__ import annotations

from typing import Any

from aiogithubapi import GitHubException
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .base import HacsBase
from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    hacs: HacsBase = hass.data[DOMAIN]

    data = {
        "entry": entry.as_dict(),
        "hacs": {
            "stage": hacs.stage,
            "version": hacs.version,
            "disabled_reason": hacs.system.disabled_reason,
            "new": hacs.status.new,
            "startup": hacs.status.startup,
            "categories": hacs.common.categories,
            "renamed_repositories": hacs.common.renamed_repositories,
            "archived_repositories": hacs.common.archived_repositories,
            "ignored_repositories": hacs.common.ignored_repositories,
            "lovelace_mode": hacs.core.lovelace_mode,
            "configuration": {},
        },
        "custom_repositories": [
            repo.data.full_name
            for repo in hacs.repositories.list_all
            if not hacs.repositories.is_default(str(repo.data.id))
        ],
        "repositories": [],
    }

    for key in (
        "appdaemon",
        "country",
        "debug",
        "dev",
        "python_script",
        "release_limit",
        "theme",
    ):
        data["hacs"]["configuration"][key] = getattr(hacs.configuration, key, None)

    for repository in hacs.repositories.list_downloaded:
        data["repositories"].append(
            {
                "data": repository.data.to_json(),
                "integration_manifest": repository.integration_manifest,
                "repository_manifest": repository.repository_manifest.to_dict(),
                "ref": repository.ref,
                "paths": {
                    "localpath": repository.localpath.replace(hacs.core.config_path, "/config"),
                    "local": repository.content.path.local.replace(
                        hacs.core.config_path, "/config"
                    ),
                    "remote": repository.content.path.remote,
                },
            }
        )

    try:
        rate_limit_response = await hacs.githubapi.rate_limit()
        data["rate_limit"] = rate_limit_response.data.as_dict
    except GitHubException as exception:
        data["rate_limit"] = str(exception)

    return async_redact_data(data, ("token",))
