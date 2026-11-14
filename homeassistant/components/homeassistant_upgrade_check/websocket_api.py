"""Websocket API for the Home Assistant Upgrade Check integration."""

from typing import Any

import probatio

from homeassistant.components import websocket_api
from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as UPDATE_DOMAIN,
)
from homeassistant.const import STATE_ON, __version__
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .feed import DATA_FEED, ReleaseNotesUnavailable
from .mock import MOCK_CORE_UPDATE_ID, MOCK_DOMAINS

CATEGORIES = ("breaking", "noteworthy", "quality_scale", "removed")
# Update entities that offer a new Home Assistant Core version, as (platform,
# unique ID).
CORE_UPDATE_ENTITIES = (
    ("hassio", "home_assistant_core_version_latest"),
    # Mock: added by update.py where there is no Supervisor.
    (DOMAIN, MOCK_CORE_UPDATE_ID),
)
ERR_UNAVAILABLE = "release_notes_unavailable"


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Register the websocket commands."""
    websocket_api.async_register_command(hass, websocket_digest)


def _core_update(hass: HomeAssistant) -> State | None:
    """Return the state of the update entity that offers a new core version."""
    entity_registry = er.async_get(hass)
    for platform, unique_id in CORE_UPDATE_ENTITIES:
        if entity_id := entity_registry.async_get_entity_id(
            UPDATE_DOMAIN, platform, unique_id
        ):
            return hass.states.get(entity_id)
    return None


def _installed_domains(hass: HomeAssistant) -> set[str]:
    """Return the domains of the integrations this installation uses."""
    # all_components holds Platform members for entity platforms; str() unwraps them.
    domains = {str(c) for c in hass.config.all_components}
    # An ignored discovery is not an installed integration.
    domains.update(
        e.domain for e in hass.config_entries.async_entries(include_ignore=False)
    )
    return domains


def _pr(pr: str) -> dict[str, str]:
    """Return the label and link of a pull request, such as frontend#123."""
    repo, _, number = pr.rpartition("#")
    return {
        "label": pr if repo else f"#{number}",
        "url": f"https://github.com/home-assistant/{repo or 'core'}/pull/{number}",
    }


def _item(entry: dict[str, Any], index: dict[str, Any], **scope: Any) -> dict[str, Any]:
    """Return a release-note entry as the frontend shows it."""
    return {
        "title": entry["title"],
        "text": entry.get("text"),
        "tier": entry.get("tier"),
        "credits": entry.get("credits", []),
        "prs": [_pr(pr) for pr in entry.get("prs", [])],
        "version": index["version"],
        "url": index["url"],
        **scope,
    }


def build_digest(
    indexes: list[dict[str, Any]],
    installed: set[str],
    running: str,
    target: str | None,
    entity_id: str | None,
) -> dict[str, Any]:
    """Collect the items that affect this installation per category, oldest first."""
    categories = []
    for key in CATEGORIES:
        items: list[dict[str, Any]] = []
        related: list[dict[str, Any]] = []
        for index in indexes:
            for entry in index[key]:
                if direct := sorted(set(entry["domains"]) & installed):
                    items.append(_item(entry, index, domains=direct, scope="domains"))
                elif entry.get("global"):
                    items.append(_item(entry, index, domains=[], scope="global"))
                elif mentioned := sorted(set(entry.get("mentions", [])) & installed):
                    related.append(
                        _item(entry, index, domains=mentioned, scope="mentions")
                    )
        if key == "quality_scale":
            # Only the tier an integration ends up with matters, not each step.
            items = list({tuple(i["domains"]): i for i in items}.values())
        categories.append(
            {"key": key, "count": len(items), "items": items, "related": related}
        )
    return {
        "running": running,
        "target": target,
        # The core update this is for, so the update dialog can match it.
        "entity_id": entity_id,
        "releases": [{"version": i["version"], "url": i["url"]} for i in indexes],
        "categories": categories,
    }


@websocket_api.require_admin
@websocket_api.websocket_command(
    {probatio.Required("type"): "homeassistant_upgrade_check/digest"}
)
@websocket_api.async_response
async def websocket_digest(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the release-note items that affect the pending core update."""
    running, target, entity_id = __version__, None, None
    if (core_update := _core_update(hass)) and core_update.state == STATE_ON:
        running = core_update.attributes[ATTR_INSTALLED_VERSION]
        target = core_update.attributes[ATTR_LATEST_VERSION]
        entity_id = core_update.entity_id
    try:
        indexes = (
            await hass.data[DATA_FEED].async_get(running, target) if target else []
        )
    except ReleaseNotesUnavailable:
        # A code, not a message: the frontend shows its own translated text.
        connection.send_error(
            msg["id"], ERR_UNAVAILABLE, "Unable to read the release notes"
        )
        return
    # Mock: drop MOCK_DOMAINS to match only what is installed.
    installed = _installed_domains(hass) | MOCK_DOMAINS
    connection.send_result(
        msg["id"], build_digest(indexes, installed, running, target, entity_id)
    )
