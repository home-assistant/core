"""Support for switches."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, override

from aioamazondevices.structures import AmazonDevice

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AmazonConfigEntry, alexa_api_call
from .entity import AmazonEntity
from .utils import async_remove_entity_from_virtual_group, async_update_unique_id

PARALLEL_UPDATES = 1

TYPE_DND = "dnd"
TYPE_COMMUNICATION = "communication"


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
    switch_type: str


DND_SWITCH: Final = AmazonSwitchEntityDescription(
    key="dnd",
    translation_key="do_not_disturb",
    # Unused: DND state is read from coordinator.dnd_states instead.
    is_on_fn=lambda device: False,
    is_available_fn=lambda device, _key: device.online,
    method="set_do_not_disturb",
    switch_type=TYPE_DND,
)
COMMUNICATION_SWITCHES: Final = (
    AmazonSwitchEntityDescription(
        key="announcements",
        translation_key="announcements",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda device: device.communication_settings["announcements"] == "ON",
        is_available_fn=lambda device, key: (
            device.online
            and device.communication_settings.get(key) is not None
            and device.communication_settings.get("communications") != "OFF"
        ),
        method="set_announcement_status",
        switch_type=TYPE_COMMUNICATION,
    ),
    AmazonSwitchEntityDescription(
        key="communications",
        translation_key="communications",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda device: device.communication_settings["communications"] == "ON",
        is_available_fn=lambda device, key: (
            device.online and device.communication_settings.get(key) is not None
        ),
        method="set_communication_status",
        switch_type=TYPE_COMMUNICATION,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Alexa Devices switches based on a config entry."""

    coordinator = entry.runtime_data

    # DND keys
    old_key = "do_not_disturb"
    new_key = "dnd"

    # Remove old DND switch from virtual groups
    await async_remove_entity_from_virtual_group(
        hass, coordinator, SWITCH_DOMAIN, old_key
    )

    # Replace unique id for DND switch
    await async_update_unique_id(hass, coordinator, SWITCH_DOMAIN, old_key, new_key)

    known_devices: set[str] = set()
    known_dnd_devices: set[str] = set()

    def _check_device() -> None:
        current_devices = set(coordinator.data)
        new_devices = current_devices - known_devices
        known_devices.update(new_devices)

        # DND state may arrive after device discovery (initial sync failure,
        # or a later push), so track it separately from `known_devices`.
        new_dnd_devices = (
            current_devices & coordinator.dnd_states.keys()
        ) - known_dnd_devices
        known_dnd_devices.update(new_dnd_devices)

        dnd_switches = [
            AmazonSwitchEntity(coordinator, serial_num, DND_SWITCH)
            for serial_num in new_dnd_devices
        ]
        communication_switches = [
            AmazonSwitchEntity(coordinator, serial_num, switch_desc)
            for switch_desc in COMMUNICATION_SWITCHES
            for serial_num in new_devices
            if switch_desc.key in coordinator.data[serial_num].communication_settings
        ]
        if dnd_switches or communication_switches:
            async_add_entities(dnd_switches + communication_switches)

    _check_device()
    entry.async_on_unload(coordinator.async_add_listener(_check_device))


class AmazonSwitchEntity(AmazonEntity, SwitchEntity):
    """Switch device."""

    entity_description: AmazonSwitchEntityDescription

    async def _switch_set_state(self, state: bool) -> None:
        """Set desired switch state."""
        method = getattr(self.coordinator.api, self.entity_description.method)

        if TYPE_CHECKING:
            assert method is not None

        async with alexa_api_call(self.coordinator):
            await method(self.device, state)
        if self.entity_description.switch_type == TYPE_DND:
            self.coordinator.set_dnd_state(self.device.serial_number, state)
        elif self.entity_description.switch_type == TYPE_COMMUNICATION:
            self.coordinator.data[self.device.serial_number].communication_settings[
                self.entity_description.key
            ] = "ON" if state else "OFF"
        self.async_write_ha_state()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._switch_set_state(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._switch_set_state(False)

    @property
    @override
    def is_on(self) -> bool:
        """Return True if switch is on."""
        if self.entity_description.switch_type == TYPE_DND:
            return self.coordinator.dnd_states.get(self.device.serial_number, False)

        return self.entity_description.is_on_fn(self.device)

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.entity_description.is_available_fn(
                self.device, self.entity_description.key
            )
            and super().available
        )
