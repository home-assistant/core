"""Support for switches."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from aioamazondevices.structures import AmazonDevice

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AmazonConfigEntry
from .entity import AmazonEntity
from .utils import (
    alexa_api_call,
    async_remove_dnd_from_virtual_group,
    async_update_unique_id,
)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class AmazonSwitchEntityDescription(SwitchEntityDescription):
    """Alexa Devices switch entity description."""

    is_on_fn: Callable[[AmazonDevice], bool]
    is_available_fn: Callable[[AmazonDevice, str], bool] = lambda device, key: (
        device.online
        and (sensor := device.sensors.get(key)) is not None
        and sensor.error is False
    )
    method: str


SWITCHES: Final = (
    AmazonSwitchEntityDescription(
        key="dnd",
        translation_key="do_not_disturb",
        is_on_fn=lambda device: bool(device.sensors["dnd"].value),
        method="set_do_not_disturb",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Alexa Devices switches based on a config entry."""

    coordinator = entry.runtime_data

    # Replace unique id for "DND" switch and remove from Speaker Group
    await async_update_unique_id(
        hass, coordinator, SWITCH_DOMAIN, "do_not_disturb", "dnd"
    )

    # Remove DND switch from virtual groups
    await async_remove_dnd_from_virtual_group(hass, coordinator)

    known_devices: set[str] = set()

    def _check_device() -> None:
        current_devices = set(coordinator.data)
        new_devices = current_devices - known_devices
        if new_devices:
            known_devices.update(new_devices)
            async_add_entities(
                AmazonSwitchEntity(coordinator, serial_num, switch_desc)
                for switch_desc in SWITCHES
                for serial_num in new_devices
                if switch_desc.key in coordinator.data[serial_num].sensors
            )

    _check_device()
    entry.async_on_unload(coordinator.async_add_listener(_check_device))


class AmazonSwitchEntity(AmazonEntity, SwitchEntity):
    """Switch device."""

    entity_description: AmazonSwitchEntityDescription

    @alexa_api_call
    async def _switch_set_state(self, state: bool) -> None:
        """Set desired switch state."""
        method = getattr(self.coordinator.api, self.entity_description.method)

        if TYPE_CHECKING:
            assert method is not None

        await method(self.device, state)
        await self.coordinator.async_request_refresh()

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

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.entity_description.is_available_fn(
                self.device, self.entity_description.key
            )
            and super().available
        )
