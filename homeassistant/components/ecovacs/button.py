"""Ecovacs button module."""
from dataclasses import dataclass

from deebot_client.capabilities import CapabilityExecute, CapabilityLifeSpan
from deebot_client.events import LifeSpan

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SUPPORTED_LIFESPANS
from .controller import EcovacsController
from .entity import (
    EcovacsCapabilityEntityDescription,
    EcovacsDescriptionEntity,
    EcovacsEntity,
)
from .util import get_supported_entitites


@dataclass(kw_only=True, frozen=True)
class EcovacsButtonEntityDescription(
    ButtonEntityDescription,
    EcovacsCapabilityEntityDescription,
):
    """Ecovacs button entity description."""


@dataclass(kw_only=True, frozen=True)
class EcovacsLifespanButtonEntityDescription(ButtonEntityDescription):
    """Ecovacs lifespan button entity description."""

    component: LifeSpan


ENTITY_DESCRIPTIONS: tuple[EcovacsButtonEntityDescription, ...] = (
    EcovacsButtonEntityDescription(
        capability_fn=lambda caps: caps.map.relocation if caps.map else None,
        key="relocate",
        translation_key="relocate",
        entity_category=EntityCategory.CONFIG,
    ),
)

LIFESPAN_ENTITY_DESCRIPTIONS = tuple(
    EcovacsLifespanButtonEntityDescription(
        component=component,
        key=f"reset_lifespan_{component.name.lower()}",
        translation_key=f"reset_lifespan_{component.name.lower()}",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    )
    for component in SUPPORTED_LIFESPANS
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    controller: EcovacsController = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[EcovacsEntity] = get_supported_entitites(
        controller, EcovacsButtonEntity, ENTITY_DESCRIPTIONS
    )
    for device in controller.devices:
        lifespan_capability = device.capabilities.life_span
        for description in LIFESPAN_ENTITY_DESCRIPTIONS:
            if description.component in lifespan_capability.types:
                entities.append(
                    EcovacsResetLifespanButtonEntity(
                        device, lifespan_capability, description
                    )
                )

    if entities:
        async_add_entities(entities)


class EcovacsButtonEntity(
    EcovacsDescriptionEntity[CapabilityExecute],
    ButtonEntity,
):
    """Ecovacs button entity."""

    entity_description: EcovacsLifespanButtonEntityDescription

    async def async_press(self) -> None:
        """Press the button."""
        await self._device.execute_command(self._capability.execute())


class EcovacsResetLifespanButtonEntity(
    EcovacsDescriptionEntity[CapabilityLifeSpan],
    ButtonEntity,
):
    """Ecovacs reset lifespan button entity."""

    entity_description: EcovacsLifespanButtonEntityDescription

    async def async_press(self) -> None:
        """Press the button."""
        await self._device.execute_command(
            self._capability.reset(self.entity_description.component)
        )
