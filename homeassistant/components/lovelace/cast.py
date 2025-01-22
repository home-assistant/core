"""Home Assistant Cast platform."""

from __future__ import annotations

from pychromecast import Chromecast
from pychromecast.const import CAST_TYPE_CHROMECAST

from homeassistant.components.cast import DOMAIN as CAST_DOMAIN
from homeassistant.components.cast.home_assistant_cast import (
    ATTR_URL_PATH,
    ATTR_VIEW_PATH,
    NO_URL_AVAILABLE_ERROR,
    SERVICE_SHOW_VIEW,
)
from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaType,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import DOMAIN, ConfigNotFound
from .dashboard import LovelaceConfig

DEFAULT_DASHBOARD = "_default_"


async def async_get_media_browser_root_object(
    hass: HomeAssistant, cast_type: str
) -> list[BrowseMedia]:
    """Create a root object for media browsing."""
    if cast_type != CAST_TYPE_CHROMECAST:
        return []
    return [
        BrowseMedia(
            title="Dashboards",
            media_class=MediaClass.APP,
            media_content_id="",
            media_content_type=DOMAIN,
            thumbnail="https://brands.home-assistant.io/_/lovelace/logo.png",
            can_play=False,
            can_expand=True,
        )
    ]


async def async_browse_media(
    hass: HomeAssistant,
    media_content_type: MediaType | str,
    media_content_id: str,
    cast_type: str,
) -> BrowseMedia | None:
    """Browse media."""
    if media_content_type != DOMAIN:
        return None

    try:
        get_url(hass, require_ssl=True, prefer_external=True)
    except NoURLAvailableError as err:
        raise BrowseError(NO_URL_AVAILABLE_ERROR) from err

    # List dashboards.
    if not media_content_id:
        children = [
            BrowseMedia(
                title="Default",
                media_class=MediaClass.APP,
                media_content_id=DEFAULT_DASHBOARD,
                media_content_type=DOMAIN,
                thumbnail="https://brands.home-assistant.io/_/lovelace/logo.png",
                can_play=True,
                can_expand=False,
            )
        ]
        for url_path in hass.data[DOMAIN]["dashboards"]:
            if url_path is None:
                continue

            info = await _get_dashboard_info(hass, url_path)
            children.append(_item_from_info(info))

        root = (await async_get_media_browser_root_object(hass, CAST_TYPE_CHROMECAST))[
            0
        ]
        root.children = children
        return root

    try:
        info = await _get_dashboard_info(hass, media_content_id)
    except ValueError as err:
        raise BrowseError(f"Dashboard {media_content_id} not found") from err

    children = []

    for view in info["views"]:
        children.append(
            BrowseMedia(
                title=view["title"],
                media_class=MediaClass.APP,
                media_content_id=f"{info['url_path']}/{view['path']}",
                media_content_type=DOMAIN,
                thumbnail="https://brands.home-assistant.io/_/lovelace/logo.png",
                can_play=True,
                can_expand=False,
            )
        )

    root = _item_from_info(info)
    root.children = children
    return root


async def async_play_media(
    hass: HomeAssistant,
    cast_entity_id: str,
    chromecast: Chromecast,
    media_type: MediaType | str,
    media_id: str,
) -> bool:
    """Play media."""
    if media_type != DOMAIN:
        return False

    if "/" in media_id:
        url_path, view_path = media_id.split("/", 1)
    else:
        url_path = media_id
        try:
            info = await _get_dashboard_info(hass, media_id)
        except ValueError as err:
            raise HomeAssistantError(f"Invalid dashboard {media_id} specified") from err
        view_path = info["views"][0]["path"] if info["views"] else "0"

    data = {
        ATTR_ENTITY_ID: cast_entity_id,
        ATTR_VIEW_PATH: view_path,
    }
    if url_path != DEFAULT_DASHBOARD:
        data[ATTR_URL_PATH] = url_path

    await hass.services.async_call(
        CAST_DOMAIN,
        SERVICE_SHOW_VIEW,
        data,
        blocking=True,
    )
    return True


async def _get_dashboard_info(hass, url_path):
    """Load a dashboard and return info on views."""
    if url_path == DEFAULT_DASHBOARD:
        url_path = None
    dashboard: LovelaceConfig | None = hass.data[DOMAIN]["dashboards"].get(url_path)

    if dashboard is None:
        raise ValueError("Invalid dashboard specified")

    try:
        config = await dashboard.async_load(False)
    except ConfigNotFound:
        config = None

    if dashboard.url_path is None:
        url_path = DEFAULT_DASHBOARD
        title = "Default"
    else:
        url_path = dashboard.url_path
        title = config.get("title", url_path) if config else url_path

    views = []
    data = {
        "title": title,
        "url_path": url_path,
        "views": views,
    }

    if config is None or "views" not in config:
        return data

    for idx, view in enumerate(config["views"]):
        path = view.get("path", f"{idx}")
        views.append(
            {
                "title": view.get("title", path),
                "path": path,
            }
        )

    return data


@callback
def _item_from_info(info: dict) -> BrowseMedia:
    """Convert dashboard info to browse item."""
    return BrowseMedia(
        title=info["title"],
        media_class=MediaClass.APP,
        media_content_id=info["url_path"],
        media_content_type=DOMAIN,
        thumbnail="https://brands.home-assistant.io/_/lovelace/logo.png",
        can_play=True,
        can_expand=len(info["views"]) > 1,
    )
