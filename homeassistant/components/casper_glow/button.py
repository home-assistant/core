"""Casper Glow integration button platform."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pycasperglow import CasperGlow

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CasperGlowConfigEntry, CasperGlowCoordinator
from .entity import CasperGlowEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class CasperGlowButtonEntityDescription(ButtonEntityDescription):
    """Describe a Casper Glow button entity."""

    press_fn: Callable[[CasperGlow], Awaitable[None]]


BUTTON_DESCRIPTIONS: tuple[CasperGlowButtonEntityDescription, ...] = (
    CasperGlowButtonEntityDescription(
        key="pause",
        translation_key="pause",
        press_fn=lambda device: device.pause(),
    ),
    CasperGlowButtonEntityDescription(
        key="resume",
        translation_key="resume",
        press_fn=lambda device: device.resume(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CasperGlowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the button platform for Casper Glow."""
    async_add_entities(
        CasperGlowButton(entry.runtime_data, description)
        for description in BUTTON_DESCRIPTIONS
    )


class CasperGlowButton(CasperGlowEntity, ButtonEntity):
    """A Casper Glow button entity."""

    entity_description: CasperGlowButtonEntityDescription

    def __init__(
        self,
        coordinator: CasperGlowCoordinator,
        description: CasperGlowButtonEntityDescription,
    ) -> None:
        """Initialize a Casper Glow button."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{format_mac(coordinator.device.address)}_{description.key}"
        )

    async def async_press(self) -> None:
        """Press the button."""
        await self._async_command(self.entity_description.press_fn(self._device))
