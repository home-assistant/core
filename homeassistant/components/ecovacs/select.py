"""Ecovacs select entity module."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic

from deebot_client.capabilities import CapabilitySetTypes
from deebot_client.device import Device
from deebot_client.events import WorkModeEvent
from deebot_client.events.water_info import WaterAmountEvent

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EcovacsConfigEntry
from .entity import EcovacsCapabilityEntityDescription, EcovacsDescriptionEntity, EventT
from .util import get_name_key, get_supported_entitites


@dataclass(kw_only=True, frozen=True)
class EcovacsSelectEntityDescription(
    SelectEntityDescription,
    EcovacsCapabilityEntityDescription,
    Generic[EventT],
):
    """Ecovacs select entity description."""

    current_option_fn: Callable[[EventT], str | None]
    options_fn: Callable[[CapabilitySetTypes], list[str]]


ENTITY_DESCRIPTIONS: tuple[EcovacsSelectEntityDescription, ...] = (
    EcovacsSelectEntityDescription[WaterAmountEvent](
        capability_fn=lambda caps: caps.water.amount if caps.water else None,
        current_option_fn=lambda e: get_name_key(e.value),
        options_fn=lambda water: [get_name_key(amount) for amount in water.types],
        key="water_amount",
        translation_key="water_amount",
        entity_category=EntityCategory.CONFIG,
    ),
    EcovacsSelectEntityDescription[WorkModeEvent](
        capability_fn=lambda caps: caps.clean.work_mode,
        current_option_fn=lambda e: get_name_key(e.mode),
        options_fn=lambda cap: [get_name_key(mode) for mode in cap.types],
        key="work_mode",
        translation_key="work_mode",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EcovacsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    controller = config_entry.runtime_data
    entities = get_supported_entitites(
        controller, EcovacsSelectEntity, ENTITY_DESCRIPTIONS
    )
    if entities:
        async_add_entities(entities)


class EcovacsSelectEntity(
    EcovacsDescriptionEntity[CapabilitySetTypes[EventT, [str], str]],
    SelectEntity,
):
    """Ecovacs select entity."""

    _attr_current_option: str | None = None
    entity_description: EcovacsSelectEntityDescription

    def __init__(
        self,
        device: Device,
        capability: CapabilitySetTypes[EventT, [str], str],
        entity_description: EcovacsSelectEntityDescription,
        **kwargs: Any,
    ) -> None:
        """Initialize entity."""
        super().__init__(device, capability, entity_description, **kwargs)
        self._attr_options = entity_description.options_fn(capability)

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(event: EventT) -> None:
            self._attr_current_option = self.entity_description.current_option_fn(event)
            self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self._device.execute_command(self._capability.set(option))
