"""Implement the Ingress Panel feature for Hass.io Add-ons."""

from http import HTTPStatus
import logging

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import IngressPanel
from aiohttp import web

from homeassistant.components import frontend
from homeassistant.components.http import HomeAssistantView, require_admin
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

from .const import MAIN_COORDINATOR
from .coordinator import HassioMainDataUpdateCoordinator
from .handler import get_supervisor_client

_LOGGER = logging.getLogger(__name__)


def async_setup_addon_panel(hass: HomeAssistant) -> None:
    """Register the add-on panel push API view."""
    hass.http.register_view(HassIOAddonPanel(hass))


@callback
def async_setup_addon_panel_coordinator(
    hass: HomeAssistant, coordinator: HassioMainDataUpdateCoordinator
) -> CALLBACK_TYPE:
    """Reconcile add-on panels registered with the frontend against coordinator data.

    Registers the panels present after the coordinator's first refresh, then keeps
    the frontend in sync with coordinator.data.panels on every following update:
    periodic refreshes, a refresh triggered by a Supervisor restart, and a post/
    delete pushed by Supervisor and cached via coordinator.async_push_panel /
    coordinator.async_push_panel_removal.

    Returns a function that unsubscribes from the coordinator.
    """
    registered: set[str] = set()

    @callback
    def _async_reconcile_panels() -> None:
        """Register or remove panels to match the coordinator's cached data."""
        panels = coordinator.data.panels
        wanted = {addon for addon, panel in panels.items() if panel.enable}

        for addon in wanted - registered:
            _register_panel(hass, addon, panels[addon])
        for addon in registered - wanted:
            frontend.async_remove_panel(hass, addon, warn_if_unknown=False)

        registered.clear()
        registered.update(wanted)

    _async_reconcile_panels()
    return coordinator.async_add_listener(_async_reconcile_panels)


class HassIOAddonPanel(HomeAssistantView):
    """Hass.io view to handle base part."""

    name = "api:hassio_push:panel"
    url = "/api/hassio_push/panel/{addon}"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize WebView."""
        self.hass = hass
        self.client = get_supervisor_client(hass)

    @require_admin
    async def post(self, request: web.Request, addon: str) -> web.Response:
        """Handle new add-on panel requests."""
        # Supervisor calls this endpoint because an add-on's panel state just
        # changed, so fetch it fresh instead of relying on the coordinator's
        # cache, which may still hold the value from before this change.
        try:
            panels = await self.client.ingress.panels()
        except SupervisorError as err:
            _LOGGER.error("Can't read panel info: %s", err)
            return web.Response(status=HTTPStatus.BAD_REQUEST)

        # Panel exists for add-on slug
        if addon not in panels or not panels[addon].enable:
            _LOGGER.error("Panel is not enabled for %s", addon)
            return web.Response(status=HTTPStatus.BAD_REQUEST)

        if (coordinator := self.hass.data.get(MAIN_COORDINATOR)) is not None:
            # Update the cache; the coordinator listener registers it with the frontend.
            coordinator.async_push_panel(addon, panels[addon])
        else:
            _register_panel(self.hass, addon, panels[addon])
        return web.Response()

    @require_admin
    async def delete(self, request: web.Request, addon: str) -> web.Response:
        """Handle remove add-on panel requests."""
        if (coordinator := self.hass.data.get(MAIN_COORDINATOR)) is not None:
            # Update the cache; the coordinator listener removes it from the frontend.
            coordinator.async_push_panel_removal(addon)
        else:
            frontend.async_remove_panel(self.hass, addon, warn_if_unknown=False)
        return web.Response()


def _register_panel(hass: HomeAssistant, addon: str, data: IngressPanel) -> None:
    """Helper to register the panel.

    Uses update=True so this is idempotent: a config entry reload can run this
    for a panel the frontend still has registered from before the reload, and
    the push API's early-startup fallback can register one before the
    coordinator's own reconciliation runs for the first time.
    """
    frontend.async_register_built_in_panel(
        hass,
        "app",
        frontend_url_path=addon,
        sidebar_title=data.title,
        sidebar_icon=data.icon,
        require_admin=data.admin,
        config={"addon": addon},
        update=True,
    )
