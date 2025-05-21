"""Support for switches."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from aioamazondevices.api import AmazonDevice

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AmazonConfigEntry, AmazonDevicesCoordinator
from .entity import AmazonEntity


@dataclass(frozen=True, kw_only=True)
class AmazonSwitchEntityDescription(SwitchEntityDescription):
    """Amazon Devices switch entity description."""

    is_on_fn: Callable[[AmazonDevice], bool]
    subkey: str


SWITCHES: Final = (
    AmazonSwitchEntityDescription(
        key="do_not_disturb",
        subkey="AUDIO_PLAYER",
        translation_key="do_not_disturb",
        is_on_fn=lambda _device: _device.do_not_disturb,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Amazon Devices switches based on a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        AmazonSwitchEntity(coordinator, serial_num, switch_desc)
        for switch_desc in SWITCHES
        for serial_num in coordinator.data
        if switch_desc.subkey in coordinator.data[serial_num].capabilities
    )


class AmazonSwitchEntity(AmazonEntity, SwitchEntity):
    """Switch device."""

    entity_description: AmazonSwitchEntityDescription

    def __init__(
        self,
        coordinator: AmazonDevicesCoordinator,
        serial_num: str,
        description: AmazonSwitchEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, serial_num)
        self.entity_description = description
        self._attr_unique_id = f"{serial_num}-{description.key}"

    async def _switch_set_state(self, state: bool) -> None:
        """Set desired switch state."""
        await self.coordinator.api.set_do_not_disturb(self.device, state)
        self.coordinator.data[self.device.serial_number].do_not_disturb = state
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._switch_set_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._switch_set_state(False)

    @property
    def is_on(self) -> bool:
        """Return True if switch is on."""
        return self.entity_description.is_on_fn(self.device)
