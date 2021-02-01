"""The Philips TV integration."""
import asyncio
from datetime import timedelta
import logging
from typing import Any, Callable, Dict

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


class PluggableAction:
    """A pluggable action handler."""

    _actions: Dict[Any, AutomationActionType] = {}

    def __init__(self, update: Callable[[], None]):
        """Initialize."""
        self._update = update

    def __bool__(self):
        """Return if we have something attached."""
        return bool(self._actions)

    @callback
    def async_attach(self, action: AutomationActionType, variables: dict):
        """Attach a device trigger for turn on."""

        @callback
        def _remove():
            del self._actions[_remove]
            self._update()

        self._actions[_remove] = (action, variables)
        self._update()

        return _remove

    async def async_run(self, context):
        """Run all turn on triggers."""
        for action, variables in self._actions.values():
            await action(variables, context)


class PhilipsTVDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Coordinator to update data."""

    api: PhilipsTV
    system: Dict[str, Any]

    def __init__(self, hass, api: PhilipsTV, system: Dict[str, Any]) -> None:
        """Set up the coordinator."""
        self.api = api
        self.system = system

        def _update_listeners():
            for update_callback in self._listeners:
                update_callback()

        self.turn_on = PluggableAction(_update_listeners)

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
