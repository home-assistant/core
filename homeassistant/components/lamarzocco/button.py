"""Button platform for La Marzocco espresso machines."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from lmcloud.exceptions import RequestNotSuccessful
from lmcloud.lm_machine import LaMarzoccoMachine

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import LaMarzoccoConfigEntry
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoButtonEntityDescription(
    LaMarzoccoEntityDescription,
    ButtonEntityDescription,
):
    """Description of a La Marzocco button."""

    press_fn: Callable[[LaMarzoccoMachine], Coroutine[Any, Any, None]]


ENTITIES: tuple[LaMarzoccoButtonEntityDescription, ...] = (
    LaMarzoccoButtonEntityDescription(
        key="start_backflush",
        translation_key="start_backflush",
        press_fn=lambda machine: machine.start_backflush(),
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
            await self.entity_description.press_fn(self.coordinator.device)
        except RequestNotSuccessful as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="button_error",
                translation_placeholders={
                    "key": self.entity_description.key,
                },
            ) from exc
        await self.coordinator.async_request_refresh()
