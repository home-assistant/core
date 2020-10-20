"""Import logic for blueprint."""
import re

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.util import yaml

from . import is_blueprint_config
from .models import Blueprint

COMMUNITY_TOPIC_PATTERN = re.compile(
    r"^https://community.home-assistant.io/t/[a-z-]+/(?P<topic>\d+)(?:/(?P<post>\d+)|)$"
)

COMMUNITY_CODE_BLOCK = re.compile(
    r'<code class="lang-(?P<syntax>[a-z]+)">(?P<content>(?:.|\n)*)</code>', re.MULTILINE
)

GITHUB_FILE_PATTERN = re.compile(
    r"^https://github.com/(?P<repository>.+)/blob/(?P<path>.+)$"
)
GITHUB_RAW_FILE_PATTERN = re.compile(r"^https://raw.githubusercontent.com/")

COMMUNITY_TOPIC_SCHEMA = vol.Schema(
    {
        "slug": str,
        "title": str,
        "post_stream": {"posts": [{"updated_at": cv.datetime, "cooked": str}]},
    },
    extra=vol.ALLOW_EXTRA,
)


def _get_github_import_url(url: str) -> str:
    """Convert a GitHub url to the raw content.

    Async friendly.
    """
    match = GITHUB_RAW_FILE_PATTERN.match(url)
    if match is not None:
        return url

    match = GITHUB_FILE_PATTERN.match(url)

    if match is None:
        raise ValueError("Not a GitHub file url")

    repo, path = match.groups()

    return f"https://raw.githubusercontent.com/{repo}/{path}"


def _get_community_post_import_url(url: str) -> str:
    """Convert a forum post url to an import url.

    Async friendly.
    """
    match = COMMUNITY_TOPIC_PATTERN.match(url)
    if match is None:
        raise ValueError("Not a topic url")

    _topic, post = match.groups()

    json_url = url

    if post is not None:
        # Chop off post part, ie /2
        json_url = json_url[: -len(post) - 1]

    json_url += ".json"

    return json_url


def _extract_blueprint_from_community_post(
    post,
) -> Blueprint:
    """Extract a blueprint from a community post JSON.

    Async friendly.
    """
    for match in COMMUNITY_CODE_BLOCK.finditer(post["cooked"]):
        block_syntax, block_content = match.groups()

        if block_syntax not in ("auto", "yaml"):
            continue

        try:
            data = yaml.parse_yaml(block_content.strip())
        except HomeAssistantError:
            if block_syntax == "yaml":
                raise

            continue

        if not is_blueprint_config(data):
            continue

        return Blueprint(data)

    return None


async def fetch_blueprint_from_community_post(
    hass: HomeAssistant, url: str
) -> Blueprint:
    """Get blueprints from a community post url.

    Method can raise aiohttp client exceptions, vol.Invalid.

    Caller needs to implement own timeout.
    """
    import_url = _get_community_post_import_url(url)
    session = aiohttp_client.async_get_clientsession(hass)

    resp = await session.get(import_url, raise_for_status=True)
    json_resp = await resp.json()
    json_resp = COMMUNITY_TOPIC_SCHEMA(json_resp)
    post = json_resp["post_stream"]["posts"][0]
    return _extract_blueprint_from_community_post(post)


async def fetch_blueprint_from_github_url(hass: HomeAssistant, url: str) -> Blueprint:
    """Get a blueprint from a github url."""
    import_url = _get_github_import_url(url)
    session = aiohttp_client.async_get_clientsession(hass)

    resp = await session.get(import_url, raise_for_status=True)
    data = yaml.parse_yaml(await resp.text())
    return Blueprint(data)


async def fetch_blueprint_from_url(hass: HomeAssistant, url: str) -> Blueprint:
    """Get a blueprint from a url."""
    for meth in (fetch_blueprint_from_community_post, fetch_blueprint_from_github_url):
        try:
            blueprint = await meth(hass, url)
            break
        except ValueError:
            pass

    else:
        raise HomeAssistantError("Unsupported url")

    if blueprint is not None:
        blueprint.update_metadata(source_url=url)

    return blueprint
