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

from .coordinator import AmazonConfigEntry, AmazonDevicesCoordinator, alexa_api_call
from .entity import AmazonEntity
from .utils import async_remove_entity_from_virtual_group, async_update_unique_id

PARALLEL_UPDATES = 1


def _dnd_is_on(
    coordinator: AmazonDevicesCoordinator,
    serial_num: str,
    entity_description_key: str,
) -> bool:
    """Return the local DND state."""
    return coordinator.dnd_states.get(serial_num, False)


def _communication_is_on(
    coordinator: AmazonDevicesCoordinator,
    serial_num: str,
    entity_description_key: str,
) -> bool:
    """Return the local communication settings state."""
    return (
        coordinator.data[serial_num].communication_settings[entity_description_key]
        == "ON"
    )


def _update_dnd_state(
    coordinator: AmazonDevicesCoordinator,
    serial_num: str,
    entity_description_key: str,
    state: bool,
) -> None:
    """Update the local DND state."""
    coordinator.set_dnd_state(serial_num, state)


def _update_communication_state(
    coordinator: AmazonDevicesCoordinator,
    serial_num: str,
    entity_description_key: str,
    state: bool,
) -> None:
    """Update the local communication settings state."""
    coordinator.data[serial_num].communication_settings[entity_description_key] = (
        "ON" if state else "OFF"
    )


@dataclass(frozen=True, kw_only=True)
class AmazonSwitchEntityDescription(SwitchEntityDescription):
    """Alexa Devices switch entity description."""

    is_on_fn: Callable[[AmazonDevicesCoordinator, str, str], bool]
    is_available_fn: Callable[[AmazonDevice, str], bool] = lambda device, key: (
        device.online
        and (sensor := device.sensors.get(key)) is not None
        and sensor.error is False
    )
    method: str
    update_state_fn: Callable[[AmazonDevicesCoordinator, str, str, bool], None]


DND_SWITCH: Final = AmazonSwitchEntityDescription(
    key="dnd",
    translation_key="do_not_disturb",
    is_on_fn=_dnd_is_on,
    is_available_fn=lambda device, _: device.online,
    method="set_do_not_disturb",
    update_state_fn=_update_dnd_state,
)
COMMUNICATION_SWITCHES: Final = (
    AmazonSwitchEntityDescription(
        key="announcements",
        translation_key="announcements",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=_communication_is_on,
        is_available_fn=lambda device, key: (
            device.online
            and device.communication_settings.get(key) is not None
            and device.communication_settings.get("communications") != "OFF"
        ),
        method="set_announcement_status",
        update_state_fn=_update_communication_state,
    ),
    AmazonSwitchEntityDescription(
        key="communications",
        translation_key="communications",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=_communication_is_on,
        is_available_fn=lambda device, key: (
            device.online and device.communication_settings.get(key) is not None
        ),
        method="set_communication_status",
        update_state_fn=_update_communication_state,
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
        known_devices.intersection_update(current_devices)
        new_devices = current_devices - known_devices

        # DND state may arrive after device discovery (initial sync failure,
        # or a later push), so track it separately from `known_devices`.
        known_dnd_devices.intersection_update(current_devices)
        new_dnd_devices = (
            current_devices & coordinator.dnd_states.keys()
        ) - known_dnd_devices

        if new_dnd_devices:
            dnd_switches = [
                AmazonSwitchEntity(coordinator, serial_num, DND_SWITCH)
                for serial_num in new_dnd_devices
            ]
            async_add_entities(dnd_switches)
            known_dnd_devices.update(new_dnd_devices)

        if new_devices:
            communication_switches = [
                AmazonSwitchEntity(coordinator, serial_num, switch_desc)
                for switch_desc in COMMUNICATION_SWITCHES
                for serial_num in new_devices
                if switch_desc.key
                in coordinator.data[serial_num].communication_settings
            ]
            async_add_entities(communication_switches)
            known_devices.update(new_devices)

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
        self.entity_description.update_state_fn(
            self.coordinator,
            self.device.serial_number,
            self.entity_description.key,
            state,
        )
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

        return self.entity_description.is_on_fn(
            self.coordinator,
            self.device.serial_number,
            self.entity_description.key,
        )

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
