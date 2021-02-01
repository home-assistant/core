"""The Philips TV integration."""
import asyncio
from datetime import timedelta
import logging
from typing import Any, Dict

from haphilipsjs import ConnectionFailure, PhilipsTV

from homeassistant.components.automation import AutomationActionType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_VERSION, CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_SYSTEM, DOMAIN

PLATFORMS = ["media_player"]

LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Philips TV component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Philips TV from a config entry."""

    tvapi = PhilipsTV(entry.data[CONF_HOST], entry.data[CONF_API_VERSION])

    coordinator = PhilipsTVDataUpdateCoordinator(hass, tvapi, entry.data[CONF_SYSTEM])

    await coordinator.async_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class PhilipsTVDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Coordinator to update data."""

    api: PhilipsTV
    system: Dict[str, Any]
    turn_on_actions: Dict[Any, AutomationActionType] = {}

    @callback
    def async_attach_turn_on_action(
        self, action: AutomationActionType, variables: dict
    ):
        """Attach a device trigger for turn on."""

        def _update():
            for update_callback in self._listeners:
                update_callback()

        @callback
        def _remove():
            del self.turn_on_actions[_remove]
            _update()

        self.turn_on_actions[_remove] = (action, variables)
        _update()

        return _remove

    async def async_turn_on(self, context):
        """Run all turn on triggers."""
        for action, variables in self.turn_on_actions.values():
            await action(variables, context)

    def __init__(self, hass, api: PhilipsTV, system: Dict[str, Any]) -> None:
        """Set up the coordinator."""
        self.api = api
        self.system = system

        def _update():
            try:
                self.api.update()
            except ConnectionFailure:
                pass

        async def _async_update() -> None:
            await self.hass.async_add_executor_job(_update)

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_method=_async_update,
            update_interval=timedelta(seconds=30),
            request_refresh_debouncer=Debouncer(
                hass, LOGGER, cooldown=2.0, immediate=False
            ),
        )
