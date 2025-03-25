"""Ecovacs button module."""

from dataclasses import dataclass

from deebot_client.capabilities import (
    CapabilityExecute,
    CapabilityExecuteTypes,
    CapabilityLifeSpan,
)
from deebot_client.commands import StationAction
from deebot_client.events import LifeSpan

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EcovacsConfigEntry
from .const import SUPPORTED_LIFESPANS, SUPPORTED_STATION_ACTIONS
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


@dataclass(kw_only=True, frozen=True)
class EcovacsStationActionButtonEntityDescription(ButtonEntityDescription):
    """Ecovacs station action button entity description."""

    action: StationAction


ENTITY_DESCRIPTIONS: tuple[EcovacsButtonEntityDescription, ...] = (
    EcovacsButtonEntityDescription(
        capability_fn=lambda caps: caps.map.relocation if caps.map else None,
        key="relocate",
        translation_key="relocate",
        entity_category=EntityCategory.CONFIG,
    ),
)

STATION_ENTITY_DESCRIPTIONS = tuple(
    EcovacsStationActionButtonEntityDescription(
        action=action,
        key=f"station_action_{action.name.lower()}",
        translation_key=f"station_action_{action.name.lower()}",
    )
    for action in SUPPORTED_STATION_ACTIONS
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
    config_entry: EcovacsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    controller = config_entry.runtime_data
    entities: list[EcovacsEntity] = get_supported_entitites(
        controller, EcovacsButtonEntity, ENTITY_DESCRIPTIONS
    )
    entities.extend(
        EcovacsResetLifespanButtonEntity(
            device, device.capabilities.life_span, description
        )
        for device in controller.devices
        for description in LIFESPAN_ENTITY_DESCRIPTIONS
        if description.component in device.capabilities.life_span.types
    )
    entities.extend(
        EcovacsStationActionButtonEntity(
            device, device.capabilities.station.action, description
        )
        for device in controller.devices
        if device.capabilities.station
        for description in STATION_ENTITY_DESCRIPTIONS
        if description.action in device.capabilities.station.action.types
    )
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


class EcovacsStationActionButtonEntity(
    EcovacsDescriptionEntity[CapabilityExecuteTypes[StationAction]],
    ButtonEntity,
):
    """Ecovacs station action button entity."""

    entity_description: EcovacsStationActionButtonEntityDescription

    async def async_press(self) -> None:
        """Press the button."""
        await self._device.execute_command(
            self._capability.execute(self.entity_description.action)
        )
