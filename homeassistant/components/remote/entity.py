"""Base entity for the Remote platform."""

from collections.abc import Iterable
import functools as ft
from typing import Any, final, override

from propcache.api import cached_property

from homeassistant.helpers.entity import ToggleEntity, ToggleEntityDescription

from .const import RemoteEntityFeature, RemoteEntityStateAttribute


class RemoteEntityDescription(ToggleEntityDescription, frozen_or_thawed=True):
    """A class that describes remote entities."""


CACHED_PROPERTIES_WITH_ATTR_ = {
    "supported_features",
    "current_activity",
    "activity_list",
}


class RemoteEntity(ToggleEntity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Base class for remote entities."""

    entity_description: RemoteEntityDescription
    _attr_activity_list: list[str] | None = None
    _attr_current_activity: str | None = None
    _attr_supported_features: RemoteEntityFeature = RemoteEntityFeature(0)

    @cached_property
    @override
    def supported_features(self) -> RemoteEntityFeature:
        """Flag supported features."""
        return self._attr_supported_features

    @cached_property
    def current_activity(self) -> str | None:
        """Active activity."""
        return self._attr_current_activity

    @cached_property
    def activity_list(self) -> list[str] | None:
        """List of available activities."""
        return self._attr_activity_list

    @final
    @property
    @override
    def state_attributes(self) -> dict[str, Any] | None:
        """Return optional state attributes."""
        if RemoteEntityFeature.ACTIVITY not in self.supported_features:
            return None

        return {
            RemoteEntityStateAttribute.ACTIVITY_LIST: self.activity_list,
            RemoteEntityStateAttribute.CURRENT_ACTIVITY: self.current_activity,
        }

    def send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send commands to a device."""
        raise NotImplementedError

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send commands to a device."""
        await self.hass.async_add_executor_job(
            ft.partial(self.send_command, command, **kwargs)
        )

    def learn_command(self, **kwargs: Any) -> None:
        """Learn a command from a device."""
        raise NotImplementedError

    async def async_learn_command(self, **kwargs: Any) -> None:
        """Learn a command from a device."""
        await self.hass.async_add_executor_job(ft.partial(self.learn_command, **kwargs))

    def delete_command(self, **kwargs: Any) -> None:
        """Delete commands from the database."""
        raise NotImplementedError

    async def async_delete_command(self, **kwargs: Any) -> None:
        """Delete commands from the database."""
        await self.hass.async_add_executor_job(
            ft.partial(self.delete_command, **kwargs)
        )
