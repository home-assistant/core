"""Support to export sensor values via RSS feed."""

from __future__ import annotations

from html import escape

from aiohttp import web
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType

CONTENT_TYPE_XML = "text/xml"
DOMAIN = "rss_feed_template"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                cv.match_all: vol.Schema(
                    {
                        vol.Optional("requires_api_password", default=True): cv.boolean,
                        vol.Optional("title"): cv.template,
                        vol.Required("items"): vol.All(
                            cv.ensure_list,
                            [
                                {
                                    vol.Optional("title"): cv.template,
                                    vol.Optional("description"): cv.template,
                                }
                            ],
                        ),
                    }
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the RSS feed template component."""
    for feeduri, feedconfig in config[DOMAIN].items():
        url = f"/api/rss_template/{feeduri}"

        requires_auth: bool = feedconfig["requires_api_password"]

        items: list[dict[str, Template]] = feedconfig["items"]
        rss_view = RssView(url, requires_auth, feedconfig.get("title"), items)
        hass.http.register_view(rss_view)

    return True


class RssView(HomeAssistantView):
    """Export states and other values as RSS."""

    name = "rss_template"

    def __init__(
        self,
        url: str,
        requires_auth: bool,
        title: Template | None,
        items: list[dict[str, Template]],
    ) -> None:
        """Initialize the rss view."""
        self.url = url
        self.requires_auth = requires_auth
        self._title = title
        self._items = items

    async def get(self, request: web.Request) -> web.Response:
        """Generate the RSS view XML."""
        response = '<?xml version="1.0" encoding="utf-8"?>\n\n'

        response += '<rss version="2.0">\n'
        response += "  <channel>\n"
        if self._title is not None:
            response += f"    <title>{escape(self._title.async_render(parse_result=False))}</title>\n"
        else:
            response += "    <title>Home Assistant</title>\n"

        response += "    <link>https://www.home-assistant.io/integrations/rss_feed_template/</link>\n"
        response += "    <description>Home automation feed</description>\n"

        for item in self._items:
            response += "    <item>\n"
            if "title" in item:
                response += "      <title>"
                response += escape(item["title"].async_render(parse_result=False))
                response += "</title>\n"
            if "description" in item:
                response += "      <description>"
                response += escape(item["description"].async_render(parse_result=False))
                response += "</description>\n"
            response += "    </item>\n"

        response += "  </channel>\n"
        response += "</rss>\n"

        return web.Response(body=response, content_type=CONTENT_TYPE_XML)
