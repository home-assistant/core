"""Register an proxy front end panel."""
import aiohttp
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_ICON, CONF_URL
import homeassistant.helpers.config_validation as cv

DOMAIN = "panel_proxy"

CONF_TITLE = "title"

CONF_RELATIVE_URL_ERROR_MSG = "Invalid relative URL. Absolute path required."
CONF_RELATIVE_URL_REGEX = r"\A/"
CONF_REQUIRE_ADMIN = "require_admin"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            vol.Schema(
                {
                    # pylint: disable=no-value-for-parameter
                    vol.Optional(CONF_TITLE): cv.string,
                    vol.Optional(CONF_ICON): cv.icon,
                    vol.Optional(CONF_REQUIRE_ADMIN, default=False): cv.boolean,
                    vol.Required(CONF_URL): vol.Any(
                        vol.Match(
                            CONF_RELATIVE_URL_REGEX, msg=CONF_RELATIVE_URL_ERROR_MSG
                        ),
                        vol.Url(),
                    ),
                }
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class PanelProxy(HomeAssistantView):
    """Reverse Proxy View."""

    requires_auth = False
    cors_allowed = True
    name = "panelproxy"

    def __init__(self, url, proxy_url):
        """Initialize view url."""
        self.url = url + r"{requested_url:.*}"
        self.proxy_url = proxy_url

    async def get(self, request, requested_url):
        """Handle GET proxy requests."""
        return await self._handle_request("GET", request, requested_url)

    async def post(self, request, requested_url):
        """Handle POST proxy requests."""
        return await self._handle_request("POST", request, requested_url)

    async def _handle_request(self, method, request, requested_url):
        """Handle proxy requests."""
        requested_url = requested_url or "/"
        headers = request.headers.copy()
        headers["Host"] = request.host
        headers["X-Real-Ip"] = request.remote
        headers["X-Forwarded-For"] = request.remote
        headers["X-Forwarded-Proto"] = request.scheme
        post_data = await request.read()
        async with aiohttp.request(
            method,
            self.proxy_url + requested_url,
            params=request.query,
            data=post_data,
            headers=headers,
        ) as resp:
            content = await resp.read()
            headers = resp.headers.copy()
            return aiohttp.web.Response(
                body=content, status=resp.status, headers=headers
            )


async def async_setup(hass, config):
    """Set up the proxy frontend panels."""
    for url_path, info in config[DOMAIN].items():
        hass.http.register_view(PanelProxy("/" + url_path, info[CONF_URL]))
        hass.components.frontend.async_register_built_in_panel(
            "iframe",
            info.get(CONF_TITLE),
            info.get(CONF_ICON),
            "proxy_" + url_path,
            {"url": "/" + url_path},
            require_admin=info[CONF_REQUIRE_ADMIN],
        )

    return True
