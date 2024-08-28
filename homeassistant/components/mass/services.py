"""Custom services for the Music Assistant integration."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from music_assistant.common.models.enums import MediaType
import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util.json import json_loads_object

from .const import DOMAIN
from .helpers import get_mass

SERVICE_SEARCH = "search"
ATTR_MEDIA_TYPE = "media_type"
ATTR_SEARCH_NAME = "name"
ATTR_SEARCH_ARTIST = "artist"
ATTR_SEARCH_ALBUM = "album"
ATTR_LIMIT = "limit"


@callback
def register_services(hass: HomeAssistant) -> None:
    """Register custom services."""

    async def handle_search(call: ServiceCall) -> ServiceResponse:
        """Handle queue_command service."""
        mass = get_mass(hass)
        search_name = call.data[ATTR_SEARCH_NAME]
        search_artist = call.data.get(ATTR_SEARCH_ARTIST)
        search_album = call.data.get(ATTR_SEARCH_ALBUM)
        if search_album and search_artist:
            search_name = f"{search_artist} - {search_album} - {search_name}"
        elif search_album:
            search_name = f"{search_album} - {search_name}"
        elif search_artist:
            search_name = f"{search_artist} - {search_name}"
        if TYPE_CHECKING:
            assert mass is not None
        result = await mass.music.search(
            search_query=search_name,
            media_types=call.data.get(ATTR_MEDIA_TYPE, MediaType.ALL),
            limit=call.data[ATTR_LIMIT],
        )

        # return limited result to prevent it being too verbose
        def compact_item(item: dict[str, Any]) -> dict[str, Any]:
            """Return compacted MediaItem dict."""
            for key in (
                "metadata",
                "provider_mappings",
                "favorite",
                "timestamp_added",
                "timestamp_modified",
                "mbid",
            ):
                item.pop(key, None)
            for key, value in item.items():
                if isinstance(value, dict):
                    item[key] = compact_item(value)
                elif isinstance(value, list):
                    for subitem in value:
                        if not isinstance(subitem, dict):
                            continue
                        compact_item(subitem)
                    # item[key] = [compact_item(x) if isinstance(x, dict) else x for x in value]
            return item

        dict_result: dict[str, list[dict[str, Any]]] = result.to_dict()
        for media_type_key in dict_result:
            for item in dict_result[media_type_key]:
                if not isinstance(item, dict):
                    continue
                compact_item(item)
        return json_loads_object(json.dumps(dict_result))

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH,
        handle_search,
        schema=vol.Schema(
            {
                vol.Required(ATTR_SEARCH_NAME): cv.string,
                vol.Optional(ATTR_MEDIA_TYPE): vol.All(
                    cv.ensure_list, [vol.Coerce(MediaType)]
                ),
                vol.Optional(ATTR_SEARCH_ARTIST): cv.string,
                vol.Optional(ATTR_SEARCH_ALBUM): cv.string,
                vol.Optional(ATTR_LIMIT, default=5): vol.Coerce(int),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
