"""Support for Snoo Switches."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from python_snoo.containers import SnooData, SnooDevice
from python_snoo.exceptions import SnooCommandException
from python_snoo.snoo import Snoo

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import SnooConfigEntry
from .entity import SnooDescriptionEntity


@dataclass(frozen=True, kw_only=True)
class SnooSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Snoo sensor."""

    value_fn: Callable[[SnooData], bool]
    set_value_fn: Callable[[Snoo, SnooDevice, SnooData, bool], Awaitable[None]]


BINARY_SENSOR_DESCRIPTIONS: list[SnooSwitchEntityDescription] = [
    SnooSwitchEntityDescription(
        key="sticky_white_noise",
        translation_key="sticky_white_noise",
        value_fn=lambda data: data.state_machine.sticky_white_noise == "on",
        set_value_fn=lambda snoo_api, device, _, state: snoo_api.set_sticky_white_noise(
            device, state
        ),
    ),
    SnooSwitchEntityDescription(
        key="hold",
        translation_key="hold",
        value_fn=lambda data: data.state_machine.hold == "on",
        set_value_fn=lambda snoo_api, device, data, state: snoo_api.set_level(
            device, data.state_machine.level, state
        ),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SnooConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Snoo device."""
    coordinators = entry.runtime_data
    async_add_entities(
        SnooSwitch(coordinator, description)
        for coordinator in coordinators.values()
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class SnooSwitch(SnooDescriptionEntity, SwitchEntity):
    """A switch using Snoo coordinator."""

    entity_description: SnooSwitchEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        try:
            await self.entity_description.set_value_fn(
                self.coordinator.snoo,
                self.coordinator.device,
                self.coordinator.data,
                True,
            )
        except SnooCommandException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_on_failed",
                translation_placeholders={"name": str(self.name), "status": "on"},
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        try:
            await self.entity_description.set_value_fn(
                self.coordinator.snoo,
                self.coordinator.device,
                self.coordinator.data,
                False,
            )
        except SnooCommandException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_off_failed",
                translation_placeholders={"name": str(self.name), "status": "off"},
            ) from err
