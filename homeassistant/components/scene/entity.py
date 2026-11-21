"""Base entity for the Scenes platform."""

import functools as ft
from typing import Any, final, override

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import callback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util
from homeassistant.util.async_ import run_callback_threadsafe


class BaseScene(RestoreEntity):
    """Base type for scenes."""

    _attr_should_poll = False
    __last_activated: str | None = None

    @property
    @final
    @override
    def state(self) -> str | None:
        """Return the state of the scene."""
        if self.__last_activated is None:
            return None
        return self.__last_activated

    @final
    def _record_activation(self) -> None:
        run_callback_threadsafe(self.hass.loop, self._async_record_activation).result()

    @final
    @callback
    def _async_record_activation(self) -> None:
        """Update the activation timestamp."""
        self.__last_activated = dt_util.utcnow().isoformat()

    @override
    async def async_internal_added_to_hass(self) -> None:
        """Call when the scene is added to hass."""
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if (
            state is not None
            and state.state is not None
            and state.state != STATE_UNAVAILABLE
        ):
            self.__last_activated = state.state

    async def _async_activate(self, **kwargs: Any) -> None:
        """Activate scene."""
        raise NotImplementedError

    def activate(self, **kwargs: Any) -> None:
        """Activate scene. Try to get entities into requested state."""
        raise NotImplementedError

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate scene. Try to get entities into requested state."""
        task = self.hass.async_add_executor_job(ft.partial(self.activate, **kwargs))
        if task:
            await task


class Scene(BaseScene):
    """A scene is a group of entities and the states we want them to be."""

    @final
    @override
    async def _async_activate(self, **kwargs: Any) -> None:
        """Activate scene.

        Should not be overridden, handle setting last press timestamp.
        """
        self._async_record_activation()
        self.async_write_ha_state()
        await self.async_activate(**kwargs)
