"""Support for switches."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Final, override

from aioamazondevices.const.devices import SPEAKER_GROUP_FAMILY
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
from .utils import async_remove_entities, async_update_unique_id

PARALLEL_UPDATES = 1


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


def _has_feature_sensor(device: AmazonDevice, sensor_key: str) -> bool:
    """Return if a supported feature of the device provides the sensor."""
    return any(
        sensor_key in feature.sensor_keys.values()
        for instances in device.features.values()
        for feature in instances.values()
    )


@dataclass(frozen=True, kw_only=True)
class AmazonSwitchEntityDescription(SwitchEntityDescription):
    """Alexa Devices switch entity description."""

    is_on_fn: Callable[[AmazonDevicesCoordinator, str, str], bool]
    is_available_fn: Callable[[AmazonDevicesCoordinator, str, str], bool]
    method: Callable[
        [AmazonDevicesCoordinator, AmazonDevice, str, bool], Awaitable[None]
    ]
    update_state_fn: Callable[[AmazonDevicesCoordinator, str, str, bool], None]


DND_SWITCH: Final = AmazonSwitchEntityDescription(
    key="dnd",
    translation_key="do_not_disturb",
    is_on_fn=lambda coordinator, serial_num, _: coordinator.dnd_states.get(
        serial_num, False
    ),
    is_available_fn=lambda coordinator, serial_num, _: (
        serial_num in coordinator.dnd_states
    ),
    method=lambda coordinator, device, _, state: coordinator.api.set_do_not_disturb(
        device, state
    ),
    update_state_fn=lambda coordinator, serial_num, _, state: coordinator.set_dnd_state(
        serial_num, state
    ),
)
COMMUNICATION_SWITCHES: Final = (
    AmazonSwitchEntityDescription(
        key="announcements",
        translation_key="announcements",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=_communication_is_on,
        is_available_fn=lambda coordinator, serial_num, key: (
            (settings := coordinator.data[serial_num].communication_settings).get(key)
            is not None
            and settings.get("communications") != "OFF"
        ),
        method=lambda coordinator, device, _, state: (
            coordinator.api.set_announcement_status(device, state)
        ),
        update_state_fn=_update_communication_state,
    ),
    AmazonSwitchEntityDescription(
        key="communications",
        translation_key="communications",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=_communication_is_on,
        is_available_fn=lambda coordinator, serial_num, key: (
            coordinator.data[serial_num].communication_settings.get(key) is not None
        ),
        method=lambda coordinator, device, _, state: (
            coordinator.api.set_communication_status(device, state)
        ),
        update_state_fn=_update_communication_state,
    ),
)
FEATURE_SWITCHES: Final = (
    AmazonSwitchEntityDescription(
        key="aqm_led",
        translation_key="aqm_led",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda coordinator, serial_num, key: (
            coordinator.sensors[serial_num][key].value == "ON"
        ),
        is_available_fn=lambda coordinator, serial_num, key: (
            (sensor := coordinator.device_sensor(serial_num, key)) is not None
            and sensor.error is False
        ),
        method=lambda coordinator, device, key, state: (
            coordinator.api.call_feature_operation(
                device,
                (sensor := coordinator.sensors[device.serial_number][key]).feature_name,
                "turnOn" if state else "turnOff",
                command_payload=None,
                instance=sensor.instance or None,
            )
        ),
        # Optimistic until Amazon pushes the new state
        update_state_fn=lambda coordinator, serial_num, key, state: setattr(
            coordinator.sensors[serial_num][key], "value", "ON" if state else "OFF"
        ),
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
    await async_remove_entities(
        hass,
        coordinator,
        SWITCH_DOMAIN,
        old_key,
        remove_fn=lambda device: device.device_family == SPEAKER_GROUP_FAMILY,
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

        async_add_entities(
            [
                AmazonSwitchEntity(coordinator, serial_num, DND_SWITCH)
                for serial_num in new_dnd_devices
            ]
            + [
                AmazonSwitchEntity(coordinator, serial_num, switch_desc)
                for switch_desc in COMMUNICATION_SWITCHES
                for serial_num in new_devices
                if switch_desc.key
                in coordinator.data[serial_num].communication_settings
            ]
            + [
                AmazonSwitchEntity(coordinator, serial_num, switch_desc)
                for switch_desc in FEATURE_SWITCHES
                for serial_num in new_devices
                if _has_feature_sensor(coordinator.data[serial_num], switch_desc.key)
            ]
        )
        known_dnd_devices.update(new_dnd_devices)
        known_devices.update(new_devices)

    _check_device()
    entry.async_on_unload(coordinator.async_add_listener(_check_device))


class AmazonSwitchEntity(AmazonEntity, SwitchEntity):
    """Switch device."""

    entity_description: AmazonSwitchEntityDescription

    async def _switch_set_state(self, state: bool) -> None:
        """Set desired switch state."""
        async with alexa_api_call(self.coordinator):
            await self.entity_description.method(
                self.coordinator, self.device, self.entity_description.key, state
            )
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
        return super().available and self.entity_description.is_available_fn(
            self.coordinator, self.device.serial_number, self.entity_description.key
        )
