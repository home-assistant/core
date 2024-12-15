"""Platform for button."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from ohme import ChargerStatus, OhmeApiClient

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OhmeConfigEntry
from .entity import OhmeEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OhmeButtonDescription(ButtonEntityDescription):
    """Class describing Ohme button entities."""

    is_supported_fn: Callable[[OhmeApiClient], bool] = lambda _: True
    press_fn: Callable[[OhmeApiClient], Awaitable[None]]
    available_fn: Callable[[OhmeApiClient], bool]


BUTTON_DESCRIPTIONS = [
    OhmeButtonDescription(
        key="approve",
        translation_key="approve",
        press_fn=lambda client: client.async_approve_charge(),
        is_supported_fn=lambda client: client.is_capable("pluginsRequireApprovalMode"),
        available_fn=lambda client: client.status is ChargerStatus.PENDING_APPROVAL,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OhmeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons."""
    coordinator = config_entry.runtime_data.charge_session_coordinator

    async_add_entities(
        OhmeButton(coordinator, description)
        for description in BUTTON_DESCRIPTIONS
        if description.is_supported_fn(coordinator.client)
    )


class OhmeButton(OhmeEntity, ButtonEntity):
    """Generic button for Ohme."""

    entity_description: OhmeButtonDescription

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.press_fn(self.coordinator.client)

    @property
    def available(self) -> bool:
        """Is entity available."""

        return super().available and self.entity_description.available_fn(
            self.coordinator.client
        )
