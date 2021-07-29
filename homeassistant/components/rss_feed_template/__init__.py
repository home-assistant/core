"""Support to export sensor values via RSS feed."""
from html import escape

from aiohttp import web
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import HTTP_OK
import homeassistant.helpers.config_validation as cv

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


def setup(hass, config):
    """Set up the RSS feed template component."""
    for (feeduri, feedconfig) in config[DOMAIN].items():
        url = f"/api/rss_template/{feeduri}"

        requires_auth = feedconfig.get("requires_api_password")

        title = feedconfig.get("title")
        if title is not None:
            title.hass = hass

        items = feedconfig.get("items")
        for item in items:
            if "title" in item:
                item["title"].hass = hass
            if "description" in item:
                item["description"].hass = hass

        rss_view = RssView(url, requires_auth, title, items)
        hass.http.register_view(rss_view)

    return True


class RssView(HomeAssistantView):
    """Export states and other values as RSS."""

    requires_auth = True
    url = None
    name = "rss_template"
    _title = None
    _items = None

    def __init__(self, url, requires_auth, title, items):
        """Initialize the rss view."""
        self.url = url
        self.requires_auth = requires_auth
        self._title = title
        self._items = items

    async def get(self, request, entity_id=None):
        """Generate the RSS view XML."""
        response = '<?xml version="1.0" encoding="utf-8"?>\n\n'

        response += "<rss>\n"
        if self._title is not None:
            response += "  <title>%s</title>\n" % escape(
                self._title.async_render(parse_result=False)
            )

        for item in self._items:
            response += "  <item>\n"
            if "title" in item:
                response += "    <title>"
                response += escape(item["title"].async_render(parse_result=False))
                response += "</title>\n"
            if "description" in item:
                response += "    <description>"
                response += escape(item["description"].async_render(parse_result=False))
                response += "</description>\n"
            response += "  </item>\n"

        response += "</rss>\n"

        return web.Response(
            body=response, content_type=CONTENT_TYPE_XML, status=HTTP_OK
        )
