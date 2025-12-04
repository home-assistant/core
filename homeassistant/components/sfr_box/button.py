"""SFR Box button platform."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from functools import wraps
from typing import TYPE_CHECKING, Any, Concatenate

from sfrbox_api.bridge import SFRBox
from sfrbox_api.exceptions import SFRBoxError
from sfrbox_api.models import SystemInfo

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import SFRConfigEntry
from .entity import SFREntity

# Coordinator is used to centralize the data updates
# but better to queue action calls to avoid conflicts
PARALLEL_UPDATES = 1


def with_error_wrapping[**_P, _R](
    func: Callable[Concatenate[SFRBoxButton, _P], Awaitable[_R]],
) -> Callable[Concatenate[SFRBoxButton, _P], Coroutine[Any, Any, _R]]:
    """Catch SFR errors."""

    @wraps(func)
    async def wrapper(
        self: SFRBoxButton,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _R:
        """Catch SFRBoxError errors and raise HomeAssistantError."""
        try:
            return await func(self, *args, **kwargs)
        except SFRBoxError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unknown_error",
                translation_placeholders={"error": str(err)},
            ) from err

    return wrapper


@dataclass(frozen=True, kw_only=True)
class SFRBoxButtonEntityDescription(ButtonEntityDescription):
    """Description for SFR Box buttons."""

    async_press: Callable[[SFRBox], Coroutine[None, None, None]]


BUTTON_TYPES: tuple[SFRBoxButtonEntityDescription, ...] = (
    SFRBoxButtonEntityDescription(
        async_press=lambda x: x.system_reboot(),
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        key="system_reboot",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SFRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons."""
    data = entry.runtime_data
    system_info = data.system.data
    if TYPE_CHECKING:
        assert system_info is not None

    entities = [
        SFRBoxButton(data.box, description, system_info) for description in BUTTON_TYPES
    ]
    async_add_entities(entities)


class SFRBoxButton(SFREntity, ButtonEntity):
    """SFR Box button."""

    entity_description: SFRBoxButtonEntityDescription

    def __init__(
        self,
        box: SFRBox,
        description: SFRBoxButtonEntityDescription,
        system_info: SystemInfo,
    ) -> None:
        """Initialize the button."""
        super().__init__(description, system_info)
        self._box = box

    @with_error_wrapping
    async def async_press(self) -> None:
        """Process the button press."""
        await self.entity_description.async_press(self._box)
