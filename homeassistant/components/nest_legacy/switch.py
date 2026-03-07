"""Switch platform for Nest devices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NestConfigEntry, NestCoordinator
from .entity import NestEntity
from .pynest.models import (
    NestCamera,
    NestDevice,
    NestDoorbell,
    NestLock,
    NestProtect,
    NestTempSensor,
    NestThermostat,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NestSwitchEntityDescription(SwitchEntityDescription):
    """Class to describe a Nest switch."""

    device_types: tuple[type[NestDevice], ...]
    unavailable_on_protobuf: bool = False


_DESCRIPTIONS: tuple[NestSwitchEntityDescription, ...] = (
    # Protect
    NestSwitchEntityDescription(
        key="night_light_enable",
        translation_key="pathlight",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:weather-night",
        device_types=(NestProtect,),
    ),
    NestSwitchEntityDescription(
        key="ntp_green_led_enable",
        translation_key="nightly_promise",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:led-off",
        device_types=(NestProtect,),
    ),
    NestSwitchEntityDescription(
        key="heads_up_enable",
        translation_key="heads_up",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:exclamation-thick",
        device_types=(NestProtect,),
    ),
    NestSwitchEntityDescription(
        key="steam_detection_enable",
        translation_key="steam_check",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:pot-steam",
        device_types=(NestProtect,),
    ),
    # Camera
    NestSwitchEntityDescription(
        key="streaming_enabled",
        translation_key="camera_streaming",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:camera",
        device_types=(NestCamera,),
    ),
    NestSwitchEntityDescription(
        key="audio_enabled",
        translation_key="audio",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:microphone",
        device_types=(NestCamera,),
    ),
    NestSwitchEntityDescription(
        key="indoor_chime_enabled",
        translation_key="indoor_chime",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:bell-ring",
        device_types=(NestDoorbell,),
    ),
    NestSwitchEntityDescription(
        key="doorbell_chime_assist_enabled",
        translation_key="visitor_announcements",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:account-voice",
        device_types=(NestDoorbell,),
        unavailable_on_protobuf=True,
    ),
    NestSwitchEntityDescription(
        key="irled_enabled",
        translation_key="night_vision",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:weather-night",
        device_types=(NestCamera,),
        entity_registry_enabled_default=False,
        unavailable_on_protobuf=True,
    ),
    NestSwitchEntityDescription(
        key="status_led_enabled",
        translation_key="status_led",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:led-on",
        device_types=(NestCamera,),
        entity_registry_enabled_default=False,
        unavailable_on_protobuf=True,
    ),
    NestSwitchEntityDescription(
        key="video_flipped",
        translation_key="image_rotation",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:rotate-180",
        device_types=(NestCamera,),
        entity_registry_enabled_default=False,
        unavailable_on_protobuf=True,
    ),
    # Lock
    NestSwitchEntityDescription(
        key="auto_relock_on",
        translation_key="auto_relock",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:lock-clock",
        device_types=(NestLock,),
    ),
    # Thermostat
    NestSwitchEntityDescription(
        key="temperature_lock",
        translation_key="temperature_lock",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:lock",
        device_types=(NestThermostat,),
    ),
    NestSwitchEntityDescription(
        key="dehumidifier_state",
        translation_key="dehumidifier",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:water-off",
        device_types=(NestThermostat,),
    ),
    NestSwitchEntityDescription(
        key="humidifier_state",
        translation_key="humidifier",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:water-plus",
        device_types=(NestThermostat,),
    ),
    # Temp Sensor
    NestSwitchEntityDescription(
        key="is_active_sensor",
        translation_key="active_sensor",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:thermometer-check",
        device_types=(NestTempSensor,),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NestConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Nest switches from a config entry."""
    coordinator = entry.runtime_data
    entities = []
    for device in coordinator.data.values():
        for description in _DESCRIPTIONS:
            if not isinstance(device, description.device_types):
                continue

            if description.unavailable_on_protobuf and device.is_protobuf:
                continue

            if (
                description.key == "indoor_chime_enabled"
                and isinstance(device, NestDoorbell)
                and not device.has_indoor_chime
            ):
                continue

            # Special check for Active Sensor switch: only if associated with thermostat
            if (
                description.key == "is_active_sensor"
                and isinstance(device, NestTempSensor)
                and not device.associated_thermostat_object_key
            ):
                continue

            if (
                hasattr(device, description.key)
                and getattr(device, description.key) is not None
            ):
                # Handle optional capabilities (like dehumidifier/humidifier)
                if description.key == "dehumidifier_state" and not getattr(
                    device, "has_dehumidifier", False
                ):
                    continue

                if description.key == "humidifier_state" and not getattr(
                    device, "has_humidifier", False
                ):
                    continue

                entities.append(NestSwitch(coordinator, device, description))

    async_add_devices(entities)


class NestSwitch(NestEntity[NestDevice], SwitchEntity):
    """Representation of a Nest Switch."""

    entity_description: NestSwitchEntityDescription

    def __init__(
        self,
        coordinator: NestCoordinator,
        device: NestDevice,
        description: NestSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{device.serial_number}-{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return getattr(self.device, self.entity_description.key, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._set_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._set_state(False)

    async def _set_state(self, state: bool) -> None:
        """Set the state of the switch."""
        key = self.entity_description.key
        await self._set_device_data({key: state})
