"""Base entity for the Notifications platform."""

from functools import partial
from typing import Any, final, override

from propcache.api import cached_property

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util
from homeassistant.util.async_ import run_callback_threadsafe

from .const import ATTR_TITLE, NotifyEntityFeature


class NotifyEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes button entities."""


class NotifyEntity(RestoreEntity):
    """Representation of a notify entity."""

    entity_description: NotifyEntityDescription
    _attr_supported_features: NotifyEntityFeature = NotifyEntityFeature(0)
    _attr_should_poll = False
    _attr_device_class: None
    _attr_state: None = None
    __last_notified_isoformat: str | None = None

    @cached_property
    @final
    @override
    def state(self) -> str | None:
        """Return the entity state."""
        return self.__last_notified_isoformat

    def __set_state(self, state: str | None) -> None:
        """Invalidate the cache of the cached property."""
        self.__dict__.pop("state", None)
        self.__last_notified_isoformat = state

    @override
    async def async_internal_added_to_hass(self) -> None:
        """Call when the notify entity is added to hass."""
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state not in (STATE_UNAVAILABLE, None):
            self.__set_state(state.state)

    @final
    def _record_notification(self) -> None:
        run_callback_threadsafe(
            self.hass.loop, self._async_record_notification
        ).result()

    @final
    @callback
    def _async_record_notification(self) -> None:
        """Record last notification."""

        self.__set_state(dt_util.utcnow().isoformat())
        self.async_write_ha_state()

    @final
    async def _async_send_message(self, **kwargs: Any) -> None:
        """Send a notification message (from e.g., service call).

        Should not be overridden, handle setting last notification timestamp.
        """
        await self.async_send_message(**kwargs)
        self._async_record_notification()

    def send_message(self, message: str, title: str | None = None) -> None:
        """Send a message."""
        raise NotImplementedError

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message."""
        kwargs: dict[str, Any] = {}
        if (
            title is not None
            and self.supported_features
            and self.supported_features & NotifyEntityFeature.TITLE
        ):
            kwargs[ATTR_TITLE] = title
        await self.hass.async_add_executor_job(
            partial(self.send_message, message, **kwargs)
        )
