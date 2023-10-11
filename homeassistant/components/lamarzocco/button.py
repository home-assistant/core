"""Button platform for La Marzocco espresso machines."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODEL_GS3_AV, MODEL_LM, MODEL_LMU
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription
from .lm_client import LaMarzoccoClient


@dataclass
class LaMarzoccoButtonEntityDescriptionMixin:
    """Description of an La Marzocco Button."""

    press_fn: Callable[[LaMarzoccoClient], Coroutine[Any, Any, None]]


@dataclass
class LaMarzoccoButtonEntityDescription(
    ButtonEntityDescription,
    LaMarzoccoEntityDescription,
    LaMarzoccoButtonEntityDescriptionMixin,
):
    """Description of an La Marzocco Button."""


ENTITIES: tuple[LaMarzoccoButtonEntityDescription, ...] = (
    LaMarzoccoButtonEntityDescription(
        key="start_backflush",
        translation_key="start_backflush",
        icon="mdi:coffee-maker",
        press_fn=lambda client: client.start_backflush(),
        extra_attributes={
            MODEL_GS3_AV: None,
            MODEL_LM: None,
            MODEL_LMU: None,
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities and services."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        LaMarzoccoButtonEntity(coordinator, hass, description)
        for description in ENTITIES
        if coordinator.lm.model_name in description.extra_attributes
    )


class LaMarzoccoButtonEntity(LaMarzoccoEntity, ButtonEntity):
    """Button supporting backflush."""

    entity_description: LaMarzoccoButtonEntityDescription

    async def async_press(self, **kwargs) -> None:
        """Press button."""
        await self.entity_description.press_fn(self._lm_client)
        await self._update_ha_state()
