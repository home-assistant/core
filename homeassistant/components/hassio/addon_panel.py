"""Implement the Ingress Panel feature for Hass.io Add-ons."""
import asyncio
import logging

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.typing import HomeAssistantType

from .const import ATTR_PANELS, ATTR_TITLE, ATTR_ICON, ATTR_ADMIN, ATTR_ENABLE
from .handler import HassioAPIError

_LOGGER = logging.getLogger(__name__)


async def async_setup_addon_panel(hass: HomeAssistantType, hassio):
    """Add-on Ingress Panel setup."""
    hassio_addon_panel = HassIOAddonPanel(hass, hassio)
    hass.http.register_view(hassio_addon_panel)

    # If panels are exists
    panels = await hassio_addon_panel.get_panels()
    if not panels:
        return

    # Register available panels
    jobs = []
    for addon, data in panels.items():
        if not data[ATTR_ENABLE]:
            continue
        jobs.append(_register_panel(hass, addon, data))

    if jobs:
        await asyncio.wait(jobs)


class HassIOAddonPanel(HomeAssistantView):
    """Hass.io view to handle base part."""

    name = "api:hassio_push:panel"
    url = "/api/hassio_push/panel/{addon}"

    def __init__(self, hass, hassio):
        """Initialize WebView."""
        self.hass = hass
        self.hassio = hassio

    async def post(self, request, addon):
        """Handle new add-on panel requests."""
        panels = await self.get_panels()

        # Panel exists for add-on slug
        if addon not in panels or not panels[addon][ATTR_ENABLE]:
            _LOGGER.error("Panel is not enable for %s", addon)
            return web.Response(status=400)
        data = panels[addon]

        # Register panel
        await _register_panel(self.hass, addon, data)
        return web.Response()

    async def delete(self, request, addon):
        """Handle remove add-on panel requests."""
        # Currently not supported by backend / frontend
        return web.Response()

    async def get_panels(self):
        """Return panels add-on info data."""
        try:
            data = await self.hassio.get_ingress_panels()
            return data[ATTR_PANELS]
        except HassioAPIError as err:
            _LOGGER.error("Can't read panel info: %s", err)
        return {}


def _register_panel(hass, addon, data):
    """Init coroutine to register the panel.

    Return coroutine.
    """
    return hass.components.panel_custom.async_register_panel(
        frontend_url_path=addon,
        webcomponent_name='hassio-main',
        sidebar_title=data[ATTR_TITLE],
        sidebar_icon=data[ATTR_ICON],
        js_url='/api/hassio/app/entrypoint.js',
        embed_iframe=True,
        require_admin=data[ATTR_ADMIN],
        config={
            "ingress": addon
        }
    )
