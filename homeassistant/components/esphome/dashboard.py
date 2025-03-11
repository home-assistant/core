"""Files to interact with an ESPHome dashboard."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.singleton import singleton
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .coordinator import ESPHomeDashboardCoordinator

_LOGGER = logging.getLogger(__name__)


KEY_DASHBOARD_MANAGER: HassKey[ESPHomeDashboardManager] = HassKey(
    "esphome_dashboard_manager"
)

STORAGE_KEY = "esphome.dashboard"
STORAGE_VERSION = 1


async def async_setup(hass: HomeAssistant) -> None:
    """Set up the ESPHome dashboard."""
    # Try to restore the dashboard manager from storage
    # to avoid reloading every ESPHome config entry after
    # Home Assistant starts and the dashboard is discovered.
    await async_get_or_create_dashboard_manager(hass)


@singleton(KEY_DASHBOARD_MANAGER, async_=True)
async def async_get_or_create_dashboard_manager(
    hass: HomeAssistant,
) -> ESPHomeDashboardManager:
    """Get the dashboard manager or create it."""
    manager = ESPHomeDashboardManager(hass)
    await manager.async_setup()
    return manager


class ESPHomeDashboardManager:
    """Class to manage the dashboard and restore it from storage."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the dashboard manager."""
        self._hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] | None = None
        self._current_dashboard: ESPHomeDashboardCoordinator | None = None
        self._cancel_shutdown: CALLBACK_TYPE | None = None

    async def async_setup(self) -> None:
        """Restore the dashboard from storage."""
        self._data = await self._store.async_load()
        if (data := self._data) and (info := data.get("info")):
            await self.async_set_dashboard_info(
                info["addon_slug"], info["host"], info["port"]
            )

    @callback
    def async_get(self) -> ESPHomeDashboardCoordinator | None:
        """Get the current dashboard."""
        return self._current_dashboard

    async def async_set_dashboard_info(
        self, addon_slug: str, host: str, port: int
    ) -> None:
        """Set the dashboard info."""
        url = f"http://{host}:{port}"
        hass = self._hass

        if cur_dashboard := self._current_dashboard:
            if cur_dashboard.addon_slug == addon_slug and cur_dashboard.url == url:
                # Do nothing if we already have this data.
                return
            # Clear and make way for new dashboard
            await cur_dashboard.async_shutdown()
            if self._cancel_shutdown is not None:
                self._cancel_shutdown()
                self._cancel_shutdown = None
            self._current_dashboard = None

        dashboard = ESPHomeDashboardCoordinator(
            hass, addon_slug, url, async_get_clientsession(hass)
        )
        await dashboard.async_request_refresh()

        self._current_dashboard = dashboard

        async def on_hass_stop(_: Event) -> None:
            await dashboard.async_shutdown()

        self._cancel_shutdown = hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, on_hass_stop
        )

        new_data = {"info": {"addon_slug": addon_slug, "host": host, "port": port}}
        if self._data != new_data:
            await self._store.async_save(new_data)

        reloads = [
            hass.config_entries.async_reload(entry.entry_id)
            for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        ]
        # Re-auth flows will check the dashboard for encryption key when the form is requested
        # but we only trigger reauth if the dashboard is available.
        if dashboard.last_update_success:
            reauths = [
                hass.config_entries.flow.async_configure(flow["flow_id"])
                for flow in hass.config_entries.flow.async_progress()
                if flow["handler"] == DOMAIN
                and flow["context"]["source"] == SOURCE_REAUTH
            ]
        else:
            reauths = []
            _LOGGER.error(
                "Dashboard unavailable; skipping reauth: %s", dashboard.last_exception
            )

        _LOGGER.debug(
            "Reloading %d and re-authenticating %d", len(reloads), len(reauths)
        )
        if reloads or reauths:
            await asyncio.gather(*reloads, *reauths)


@callback
def async_get_dashboard(hass: HomeAssistant) -> ESPHomeDashboardCoordinator | None:
    """Get an instance of the dashboard if set.

    This is only safe to call after `async_setup` has been completed.

    It should not be called from the config flow because there is a race
    where manager can be an asyncio.Event instead of the actual manager
    because the singleton decorator is not yet done.
    """
    manager = hass.data.get(KEY_DASHBOARD_MANAGER)
    return manager.async_get() if manager else None


async def async_set_dashboard_info(
    hass: HomeAssistant, addon_slug: str, host: str, port: int
) -> None:
    """Set the dashboard info."""
    manager = await async_get_or_create_dashboard_manager(hass)
    await manager.async_set_dashboard_info(addon_slug, host, port)
