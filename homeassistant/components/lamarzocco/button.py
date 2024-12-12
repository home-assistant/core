"""Button platform for La Marzocco espresso machines."""

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from pylamarzocco.exceptions import RequestNotSuccessful

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import LaMarzoccoConfigEntry, LaMarzoccoUpdateCoordinator
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription

PARALLEL_UPDATES = 1
BACKFLUSH_ENABLED_DURATION = 15


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoButtonEntityDescription(
    LaMarzoccoEntityDescription,
    ButtonEntityDescription,
):
    """Description of a La Marzocco button."""

    press_fn: Callable[[LaMarzoccoUpdateCoordinator], Coroutine[Any, Any, None]]


async def async_backflush_and_update(coordinator: LaMarzoccoUpdateCoordinator) -> None:
    """Press backflush button."""
    await coordinator.device.start_backflush()
    # lib will set state optimistically
    coordinator.async_set_updated_data(None)
    # backflush is enabled for 15 seconds
    # then turns off automatically
    await asyncio.sleep(BACKFLUSH_ENABLED_DURATION + 1)
    await coordinator.async_request_refresh()


ENTITIES: tuple[LaMarzoccoButtonEntityDescription, ...] = (
    LaMarzoccoButtonEntityDescription(
        key="start_backflush",
        translation_key="start_backflush",
        press_fn=async_backflush_and_update,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMarzoccoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities."""

    coordinator = entry.runtime_data
    async_add_entities(
        LaMarzoccoButtonEntity(coordinator, description)
        for description in ENTITIES
        if description.supported_fn(coordinator)
    )


class LaMarzoccoButtonEntity(LaMarzoccoEntity, ButtonEntity):
    """La Marzocco Button Entity."""

    entity_description: LaMarzoccoButtonEntityDescription

    async def async_press(self) -> None:
        """Press button."""
        try:
            await self.entity_description.press_fn(self.coordinator)
        except RequestNotSuccessful as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="button_error",
                translation_placeholders={
                    "key": self.entity_description.key,
                },
            ) from exc
