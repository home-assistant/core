"""Switch entities for Beatbot."""

from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BeatbotConfigEntry
from .coordinator import BeatbotCoordinator
from .entity import BeatbotEntity
from .iot.const import INTERFACE_CHILD_LOCK, INTERFACE_VOICE_DISTURB


@dataclass(frozen=True)
class BeatbotSwitchDescription:
    """Describe a Beatbot switch capability."""

    interface_info: str
    data_field: str
    translation_key: str


SWITCH_DESCRIPTIONS = (
    BeatbotSwitchDescription(INTERFACE_CHILD_LOCK, "child_lock", "child_lock"),
    BeatbotSwitchDescription(INTERFACE_VOICE_DISTURB, "voice_disturb", "voice_disturb"),
)


class BeatbotSwitch(BeatbotEntity, SwitchEntity):
    """A boolean switch advertised by the device capability list."""

    def __init__(
        self,
        coordinator: BeatbotCoordinator,
        device_id: str,
        description: BeatbotSwitchDescription,
    ) -> None:
        """Initialize a Beatbot switch."""
        super().__init__(coordinator, device_id)
        self._description = description
        self._attr_unique_id = f"{device_id}_{description.data_field}"
        self._attr_translation_key = description.translation_key

    @property
    @override
    def available(self) -> bool:
        """Return whether the switch can be controlled."""
        return self.data.is_online and self.coordinator.last_update_success

    @property
    @override
    def is_on(self) -> bool:
        """Return the switch state."""
        value = getattr(self.data, self._description.data_field)
        return value is True or value in {1, "on"}

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self._async_set_enabled("on")

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self._async_set_enabled("off")

    async def _async_set_enabled(self, enabled: str) -> None:
        await self._async_send_command(
            self.coordinator.api.set_switch(
                self._device_id,
                self._description.interface_info,
                enabled,
            )
        )
        self.coordinator.async_schedule_device_state_refresh(self._device_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BeatbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Beatbot switches."""
    coordinator = entry.runtime_data.coordinator
    entities = []
    for device_id, device in coordinator.data.items():
        for description in SWITCH_DESCRIPTIONS:
            capability = device.capabilities.get(description.interface_info)
            if capability is not None and not capability.non_controllable:
                entities.append(BeatbotSwitch(coordinator, device_id, description))
    async_add_entities(entities)
