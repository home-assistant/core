"""Implement the Ingress Panel feature for Hass.io Add-ons."""

from http import HTTPStatus
import logging

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import IngressPanel
from aiohttp import web

from homeassistant.components import frontend
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .handler import get_supervisor_client

_LOGGER = logging.getLogger(__name__)


async def async_setup_addon_panel(hass: HomeAssistant) -> None:
    """Add-on Ingress Panel setup."""
    hassio_addon_panel = HassIOAddonPanel(hass)
    hass.http.register_view(hassio_addon_panel)

    # If panels are exists
    if not (panels := await hassio_addon_panel.get_panels()):
        return

    # Register available panels
    for addon, data in panels.items():
        if not data.enable:
            continue
        _register_panel(hass, addon, data)


class HassIOAddonPanel(HomeAssistantView):
    """Hass.io view to handle base part."""

    name = "api:hassio_push:panel"
    url = "/api/hassio_push/panel/{addon}"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize WebView."""
        self.hass = hass
        self.client = get_supervisor_client(hass)

    async def post(self, request: web.Request, addon: str) -> web.Response:
        """Handle new add-on panel requests."""
        panels = await self.get_panels()

        # Panel exists for add-on slug
        if addon not in panels or not panels[addon].enable:
            _LOGGER.error("Panel is not enabled for %s", addon)
            return web.Response(status=HTTPStatus.BAD_REQUEST)

        # Register panel
        _register_panel(self.hass, addon, panels[addon])
        return web.Response()

    async def delete(self, request: web.Request, addon: str) -> web.Response:
        """Handle remove add-on panel requests."""
        frontend.async_remove_panel(self.hass, addon)
        return web.Response()

    async def get_panels(self) -> dict[str, IngressPanel]:
        """Return panels add-on info data."""
        try:
            return await self.client.ingress.panels()
        except SupervisorError as err:
            _LOGGER.error("Can't read panel info: %s", err)
        return {}


def _register_panel(hass: HomeAssistant, addon: str, data: IngressPanel):
    """Helper to register the panel."""
    frontend.async_register_built_in_panel(
        hass,
        "app",
        frontend_url_path=addon,
        sidebar_title=data.title,
        sidebar_icon=data.icon,
        require_admin=data.admin,
        config={"addon": addon},
    )
