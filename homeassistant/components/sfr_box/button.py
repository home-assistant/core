"""SFR Box button platform."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from functools import wraps
from typing import Any, Concatenate, ParamSpec, TypeVar

from sfrbox_api.bridge import SFRBox
from sfrbox_api.exceptions import SFRBoxError
from sfrbox_api.models import SystemInfo

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .models import DomainData

_T = TypeVar("_T")
_P = ParamSpec("_P")


def with_error_wrapping(
    func: Callable[Concatenate[SFRBoxButton, _P], Awaitable[_T]]
) -> Callable[Concatenate[SFRBoxButton, _P], Coroutine[Any, Any, _T]]:
    """Catch SFR errors."""

    @wraps(func)
    async def wrapper(
        self: SFRBoxButton,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _T:
        """Catch SFRBoxError errors and raise HomeAssistantError."""
        try:
            return await func(self, *args, **kwargs)
        except SFRBoxError as err:
            raise HomeAssistantError(err) from err

    return wrapper


@dataclass
class SFRBoxButtonMixin:
    """Mixin for SFR Box buttons."""

    async_press: Callable[[SFRBox], Coroutine[None, None, None]]


@dataclass
class SFRBoxButtonEntityDescription(ButtonEntityDescription, SFRBoxButtonMixin):
    """Description for SFR Box buttons."""


BUTTON_TYPES: tuple[SFRBoxButtonEntityDescription, ...] = (
    SFRBoxButtonEntityDescription(
        async_press=lambda x: x.system_reboot(),
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        key="system_reboot",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the buttons."""
    data: DomainData = hass.data[DOMAIN][entry.entry_id]

    entities = [
        SFRBoxButton(data.box, description, data.system.data)
        for description in BUTTON_TYPES
    ]
    async_add_entities(entities)


class SFRBoxButton(ButtonEntity):
    """Mixin for button specific attributes."""

    entity_description: SFRBoxButtonEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        box: SFRBox,
        description: SFRBoxButtonEntityDescription,
        system_info: SystemInfo,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._box = box
        self._attr_unique_id = f"{system_info.mac_addr}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system_info.mac_addr)},
        )

    @with_error_wrapping
    async def async_press(self) -> None:
        """Process the button press."""
        await self.entity_description.async_press(self._box)
