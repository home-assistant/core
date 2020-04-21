"""Config flow to configure the AIS Spotify Service component."""

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.components.http.view import HomeAssistantView
import aiohttp
import logging
from .const import DOMAIN

G_SPOTIFY_AUTH_URL = None
_LOGGER = logging.getLogger(__name__)

AUTH_CALLBACK_PATH = "/api/ais_spotify_service/authorize"
AUTH_CALLBACK_NAME = "ais_spotify_service:authorize"


def setUrl(url):
    global G_SPOTIFY_AUTH_URL
    G_SPOTIFY_AUTH_URL = url


@callback
def configured_service(hass):
    """Return a set of the configured hosts."""
    return set("spotify" for entry in hass.config_entries.async_entries(DOMAIN))


class AuthorizationCallbackView(HomeAssistantView):
    requires_auth = False
    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME

    async def get(self, request):
        global G_SPOTIFY_AUTH_URL

        hass = request.app["hass"]
        flow_id = request.query["flow_id"]

        try:
            step_ip = request.query["step_ip"]
        except Exception:
            step_ip = 0

        # add the REAL_IP and FLOW_ID to Spotify Auth URL and redirect to Spotify for authentication
        if step_ip == "1":
            real_ip = request.url.host
            G_SPOTIFY_AUTH_URL = G_SPOTIFY_AUTH_URL.replace("real_ip_place", real_ip)
            G_SPOTIFY_AUTH_URL = G_SPOTIFY_AUTH_URL.replace("flow_id_place", flow_id)
            js_text = (
                "<script>window.location.href='" + G_SPOTIFY_AUTH_URL + "'</script>"
            )
            return aiohttp.web_response.Response(
                headers={"content-type": "text/html"}, text=js_text
            )

        # the call was from ais-dom finish the integration
        hass.async_create_task(
            hass.config_entries.flow.async_configure(flow_id=flow_id, user_input="ok")
        )
        # js_text =  "<script>window.close()</script>"
        js_text = (
            "<script>window.location.href='/config/integrations/dashboard'</script>"
        )
        return aiohttp.web_response.Response(
            headers={"content-type": "text/html"}, text=js_text
        )


@config_entries.HANDLERS.register(DOMAIN)
class SpotifyFlowHandler(config_entries.ConfigFlow):
    """Spotify config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize zone configuration flow."""
        pass

    async def async_step_discovery(self, discovery_info):
        """Handle a discovered Spotify integration."""
        # Abort if other flows in progress or an entry already exists
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        # Show selection form
        return self.async_show_form(step_id="user")

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:
            return await self.async_step_init(user_input=None)
        return self.async_show_form(step_id="confirm", errors=errors)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:

            # register view
            self.hass.http.register_view(AuthorizationCallbackView)
            # go to external step
            return self.async_external_step(
                step_id="auth",
                url=AUTH_CALLBACK_PATH
                + "?flow_id={}&step_ip={} ".format(self.flow_id, 1),
            )
        return self.async_show_form(step_id="init", errors=errors)

    async def async_step_auth(self, user_input=None):
        """Received code for authentication."""

        # Flow has been triggered from AIS-dom website
        if user_input == "ok":
            return self.async_external_step_done(next_step_id="finish")
        # starting the flow from app
        return self.async_external_step(step_id="auth", url=G_SPOTIFY_AUTH_URL)

    async def async_step_finish(self, user_input=None):
        """Create the integration."""
        return self.async_create_entry(title="Dostęp do Spotify", data={"ok": 1})
