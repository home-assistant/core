"""Implement the Ingress Panel feature for Hass.io Add-ons."""

from http import HTTPStatus
import logging
from typing import Any

from aiohttp import web

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import ATTR_ICON
from homeassistant.core import HomeAssistant

from .const import ATTR_ADMIN, ATTR_ENABLE, ATTR_PANELS, ATTR_TITLE
from .handler import HassIO, HassioAPIError

_LOGGER = logging.getLogger(__name__)


async def async_setup_addon_panel(hass: HomeAssistant, hassio: HassIO) -> None:
    """Add-on Ingress Panel setup."""
    hassio_addon_panel = HassIOAddonPanel(hass, hassio)
    hass.http.register_view(hassio_addon_panel)

    # If panels are exists
    if not (panels := await hassio_addon_panel.get_panels()):
        return

    # Register available panels
    for addon, data in panels.items():
        if not data[ATTR_ENABLE]:
            continue
        # _register_panel never suspends and is only
        # a coroutine because it would be a breaking change
        # to make it a normal function
        await _register_panel(hass, addon, data)


class HassIOAddonPanel(HomeAssistantView):
    """Hass.io view to handle base part."""

    name = "api:hassio_push:panel"
    url = "/api/hassio_push/panel/{addon}"

    def __init__(self, hass: HomeAssistant, hassio: HassIO) -> None:
        """Initialize WebView."""
        self.hass = hass
        self.hassio = hassio

    async def post(self, request: web.Request, addon: str) -> web.Response:
        """Handle new add-on panel requests."""
        panels = await self.get_panels()

        # Panel exists for add-on slug
        if addon not in panels or not panels[addon][ATTR_ENABLE]:
            _LOGGER.error("Panel is not enable for %s", addon)
            return web.Response(status=HTTPStatus.BAD_REQUEST)
        data = panels[addon]

        # Register panel
        await _register_panel(self.hass, addon, data)
        return web.Response()

    async def delete(self, request: web.Request, addon: str) -> web.Response:
        """Handle remove add-on panel requests."""
        frontend.async_remove_panel(self.hass, addon)
        return web.Response()

    async def get_panels(self) -> dict:
        """Return panels add-on info data."""
        try:
            data = await self.hassio.get_ingress_panels()
            return data[ATTR_PANELS]
        except HassioAPIError as err:
            _LOGGER.error("Can't read panel info: %s", err)
        return {}


async def _register_panel(
    hass: HomeAssistant, addon: str, data: dict[str, Any]
) -> None:
    """Init coroutine to register the panel."""
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=addon,
        webcomponent_name="hassio-main",
        sidebar_title=data[ATTR_TITLE],
        sidebar_icon=data[ATTR_ICON],
        js_url="/api/hassio/app/entrypoint.js",
        embed_iframe=True,
        require_admin=data[ATTR_ADMIN],
        config={"ingress": addon},
    )
