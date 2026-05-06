"""Switch platform for SVS Subwoofer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SVSConfigEntry
from .coordinator import SVSSubwooferCoordinator


@dataclass(frozen=True, kw_only=True)
class SVSSwitchEntityDescription(SwitchEntityDescription):
    """Describes SVS switch entity."""

    svs_param: str


SWITCH_DESCRIPTIONS: tuple[SVSSwitchEntityDescription, ...] = (
    SVSSwitchEntityDescription(
        key="lpf_enable",
        translation_key="lpf_enable",
        svs_param="LOW_PASS_FILTER_ENABLE",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:tune-vertical",
    ),
    SVSSwitchEntityDescription(
        key="peq1_enable",
        translation_key="peq1_enable",
        svs_param="PEQ1_ENABLE",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:equalizer",
    ),
    SVSSwitchEntityDescription(
        key="peq2_enable",
        translation_key="peq2_enable",
        svs_param="PEQ2_ENABLE",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:equalizer",
    ),
    SVSSwitchEntityDescription(
        key="peq3_enable",
        translation_key="peq3_enable",
        svs_param="PEQ3_ENABLE",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:equalizer",
    ),
    SVSSwitchEntityDescription(
        key="room_gain_enable",
        translation_key="room_gain_enable",
        svs_param="ROOM_GAIN_ENABLE",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:home-sound-in",
    ),
    SVSSwitchEntityDescription(
        key="polarity",
        translation_key="polarity",
        svs_param="POLARITY",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:swap-horizontal",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SVSConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SVS switch entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        SVSSwitchEntity(coordinator, description) for description in SWITCH_DESCRIPTIONS
    )


class SVSSwitchEntity(CoordinatorEntity[SVSSubwooferCoordinator], SwitchEntity):
    """Representation of an SVS switch entity."""

    _attr_has_entity_name = True
    entity_description: SVSSwitchEntityDescription

    def __init__(
        self,
        coordinator: SVSSubwooferCoordinator,
        description: SVSSwitchEntityDescription,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        value = self.coordinator.data.get(self.entity_description.svs_param)
        if value is None:
            return None
        return bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.async_send_command(self.entity_description.svs_param, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.async_send_command(self.entity_description.svs_param, 0)
