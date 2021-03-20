"""Import logic for blueprint."""
from __future__ import annotations

from dataclasses import dataclass
import html
import re

import voluptuous as vol
import yarl

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.util import yaml

from .models import Blueprint
from .schemas import is_blueprint_config

COMMUNITY_TOPIC_PATTERN = re.compile(
    r"^https://community.home-assistant.io/t/[a-z0-9-]+/(?P<topic>\d+)(?:/(?P<post>\d+)|)$"
)

COMMUNITY_CODE_BLOCK = re.compile(
    r'<code class="lang-(?P<syntax>[a-z]+)">(?P<content>(?:.|\n)*)</code>', re.MULTILINE
)

GITHUB_FILE_PATTERN = re.compile(
    r"^https://github.com/(?P<repository>.+)/blob/(?P<path>.+)$"
)

COMMUNITY_TOPIC_SCHEMA = vol.Schema(
    {
        "slug": str,
        "title": str,
        "post_stream": {"posts": [{"updated_at": cv.datetime, "cooked": str}]},
    },
    extra=vol.ALLOW_EXTRA,
)


class UnsupportedUrl(HomeAssistantError):
    """When the function doesn't support the url."""


@dataclass(frozen=True)
class ImportedBlueprint:
    """Imported blueprint."""

    suggested_filename: str
    raw_data: str
    blueprint: Blueprint


def _get_github_import_url(url: str) -> str:
    """Convert a GitHub url to the raw content.

    Async friendly.
    """
    if url.startswith("https://raw.githubusercontent.com/"):
        return url

    match = GITHUB_FILE_PATTERN.match(url)

    if match is None:
        raise UnsupportedUrl("Not a GitHub file url")

    repo, path = match.groups()

    return f"https://raw.githubusercontent.com/{repo}/{path}"


def _get_community_post_import_url(url: str) -> str:
    """Convert a forum post url to an import url.

    Async friendly.
    """
    match = COMMUNITY_TOPIC_PATTERN.match(url)
    if match is None:
        raise UnsupportedUrl("Not a topic url")

    _topic, post = match.groups()

    json_url = url

    if post is not None:
        # Chop off post part, ie /2
        json_url = json_url[: -len(post) - 1]

    json_url += ".json"

    return json_url


def _extract_blueprint_from_community_topic(
    url: str,
    topic: dict,
) -> ImportedBlueprint | None:
    """Extract a blueprint from a community post JSON.

    Async friendly.
    """
    block_content = None
    blueprint = None
    post = topic["post_stream"]["posts"][0]

    for match in COMMUNITY_CODE_BLOCK.finditer(post["cooked"]):
        block_syntax, block_content = match.groups()

        if block_syntax not in ("auto", "yaml"):
            continue

        block_content = html.unescape(block_content.strip())

        try:
            data = yaml.parse_yaml(block_content)
        except HomeAssistantError:
            if block_syntax == "yaml":
                raise

            continue

        if not is_blueprint_config(data):
            continue

        blueprint = Blueprint(data)
        break

    if blueprint is None:
        raise HomeAssistantError(
            "No valid blueprint found in the topic. Blueprint syntax blocks need to be marked as YAML or no syntax."
        )

    return ImportedBlueprint(
        f'{post["username"]}/{topic["slug"]}', block_content, blueprint
    )


async def fetch_blueprint_from_community_post(
    hass: HomeAssistant, url: str
) -> ImportedBlueprint | None:
    """Get blueprints from a community post url.

    Method can raise aiohttp client exceptions, vol.Invalid.

    Caller needs to implement own timeout.
    """
    import_url = _get_community_post_import_url(url)
    session = aiohttp_client.async_get_clientsession(hass)

    resp = await session.get(import_url, raise_for_status=True)
    json_resp = await resp.json()
    json_resp = COMMUNITY_TOPIC_SCHEMA(json_resp)
    return _extract_blueprint_from_community_topic(url, json_resp)


async def fetch_blueprint_from_github_url(
    hass: HomeAssistant, url: str
) -> ImportedBlueprint:
    """Get a blueprint from a github url."""
    import_url = _get_github_import_url(url)
    session = aiohttp_client.async_get_clientsession(hass)

    resp = await session.get(import_url, raise_for_status=True)
    raw_yaml = await resp.text()
    data = yaml.parse_yaml(raw_yaml)
    blueprint = Blueprint(data)

    parsed_import_url = yarl.URL(import_url)
    suggested_filename = f"{parsed_import_url.parts[1]}/{parsed_import_url.parts[-1]}"
    if suggested_filename.endswith(".yaml"):
        suggested_filename = suggested_filename[:-5]

    return ImportedBlueprint(suggested_filename, raw_yaml, blueprint)


async def fetch_blueprint_from_github_gist_url(
    hass: HomeAssistant, url: str
) -> ImportedBlueprint:
    """Get a blueprint from a Github Gist."""
    if not url.startswith("https://gist.github.com/"):
        raise UnsupportedUrl("Not a GitHub gist url")

    parsed_url = yarl.URL(url)
    session = aiohttp_client.async_get_clientsession(hass)

    resp = await session.get(
        f"https://api.github.com/gists/{parsed_url.parts[2]}",
        headers={"Accept": "application/vnd.github.v3+json"},
        raise_for_status=True,
    )
    gist = await resp.json()

    blueprint = None
    filename = None
    content = None

    for filename, info in gist["files"].items():
        if not filename.endswith(".yaml"):
            continue

        content = info["content"]
        data = yaml.parse_yaml(content)

        if not is_blueprint_config(data):
            continue

        blueprint = Blueprint(data)
        break

    if blueprint is None:
        raise HomeAssistantError(
            "No valid blueprint found in the gist. The blueprint file needs to end with '.yaml'"
        )

    return ImportedBlueprint(
        f"{gist['owner']['login']}/{filename[:-5]}", content, blueprint
    )


async def fetch_blueprint_from_url(hass: HomeAssistant, url: str) -> ImportedBlueprint:
    """Get a blueprint from a url."""
    for func in (
        fetch_blueprint_from_community_post,
        fetch_blueprint_from_github_url,
        fetch_blueprint_from_github_gist_url,
    ):
        try:
            imported_bp = await func(hass, url)
            imported_bp.blueprint.update_metadata(source_url=url)
            return imported_bp
        except UnsupportedUrl:
            pass

    raise HomeAssistantError("Unsupported url")
