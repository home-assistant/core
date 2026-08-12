"""Fan for Midea."""

from dataclasses import dataclass
from typing import Any, cast, override

from midealocal.const import DeviceType
from midealocal.devices.b6 import MideaB6Device
from midealocal.devices.ce import MideaCEDevice
from midealocal.devices.fa import MideaFADevice
from midealocal.devices.x40 import MideaX40Device

from homeassistant.components.fan import (
    FanEntity,
    FanEntityDescription,
    FanEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MideaConfigEntry, MideaEntity, midea_api_call

PARALLEL_UPDATES = 0

type MideaFanDevice = MideaFADevice | MideaB6Device | MideaCEDevice | MideaX40Device
type MideaCombinedTurnOnDevice = MideaFADevice | MideaB6Device


@dataclass(kw_only=True, frozen=True)
class MideaFanEntityDescription(FanEntityDescription):
    """Description for a Midea fan entity."""

    models: list[DeviceType]
    supported_features: FanEntityFeature
    # False to only powers the device on
    # True to also set fan_speed and mode
    has_combined_turn_on: bool = False
    is_on_attribute: str


FANS: list[MideaFanEntityDescription] = [
    MideaFanEntityDescription(
        key="fan",
        models=[DeviceType.FA],
        supported_features=(
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.OSCILLATE
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        ),
        is_on_attribute="power",
        has_combined_turn_on=True,
    ),
    MideaFanEntityDescription(
        key="fan",
        models=[DeviceType.B6],
        supported_features=(
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        ),
        is_on_attribute="power",
        has_combined_turn_on=True,
    ),
    MideaFanEntityDescription(
        key="fan",
        models=[DeviceType.CE],
        supported_features=(
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        ),
        is_on_attribute="power",
    ),
    MideaFanEntityDescription(
        key="fan",
        models=[DeviceType.X40],
        supported_features=(
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        ),
        is_on_attribute="fan_speed",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MideaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up fans for device."""
    device = config_entry.runtime_data

    async_add_entities(
        MideaFan(cast(MideaFanDevice, device), description)
        for description in FANS
        if device.device_type in description.models
    )


class MideaFan(MideaEntity, FanEntity):
    """Midea Fan Entries Base Class."""

    _device: MideaFanDevice
    entity_description: MideaFanEntityDescription

    def __init__(
        self, device: MideaFanDevice, description: MideaFanEntityDescription
    ) -> None:
        """Midea Fan entity init."""
        super().__init__(device, description)
        self._attr_supported_features = description.supported_features
        self._attr_speed_count = device.speed_count
        self._attr_preset_modes = device.preset_modes

    @property
    @override
    def is_on(self) -> bool | None:
        """Midea Fan is on."""
        value = self._device.get_attribute(self.entity_description.is_on_attribute)
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value > 0
        return None

    @property
    @override
    def preset_mode(self) -> str | None:
        """Midea Fan preset mode."""
        mode = self._device.get_attribute("mode")
        if not isinstance(mode, str):
            return None
        return mode

    @property
    @override
    def percentage(self) -> int | None:
        """Midea Fan percentage."""
        fan_speed = self._device.get_attribute("fan_speed")
        if not isinstance(fan_speed, int) or not fan_speed:
            return None
        return round(fan_speed * self.percentage_step)

    @property
    @override
    def oscillating(self) -> bool | None:
        """Midea Fan oscillating."""
        oscillate = self._device.get_attribute("oscillate")
        if not isinstance(oscillate, bool):
            return None
        return oscillate

    @override
    def oscillate(self, oscillating: bool) -> None:
        """Midea Fan oscillate."""
        with midea_api_call():
            self._device.set_attribute(attr="oscillate", value=oscillating)

    @override
    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Midea Fan turn on."""
        if self.entity_description.has_combined_turn_on:
            fan_speed = round(percentage / self.percentage_step) if percentage else None
            with midea_api_call():
                cast("MideaCombinedTurnOnDevice", self._device).turn_on(
                    fan_speed=fan_speed, mode=preset_mode
                )
            return
        if self.entity_description.is_on_attribute == "power":
            with midea_api_call():
                self._device.set_attribute(attr="power", value=True)
            return
        self.set_percentage(round(percentage or self.percentage_step))

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Midea Fan turn off."""
        off_value: bool | int = (
            False if self.entity_description.is_on_attribute == "power" else 0
        )
        with midea_api_call():
            self._device.set_attribute(
                attr=self.entity_description.is_on_attribute, value=off_value
            )

    @override
    def set_percentage(self, percentage: int) -> None:
        """Midea Fan set percentage."""
        fan_speed = round(percentage / self.percentage_step)
        with midea_api_call():
            self._device.set_attribute(attr="fan_speed", value=fan_speed)

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Midea Fan async set percentage."""
        if percentage == 0:
            await self.async_turn_off()
        else:
            await self.hass.async_add_executor_job(self.set_percentage, percentage)

    @override
    def set_preset_mode(self, preset_mode: str) -> None:
        """Midea Fan set preset mode."""
        with midea_api_call():
            self._device.set_attribute(attr="mode", value=preset_mode)
