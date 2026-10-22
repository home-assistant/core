"""Humidifier for Midea."""

from dataclasses import dataclass
from typing import Any, override

from midealocal.const import DeviceType
from midealocal.devices.a1 import MideaA1Device
from midealocal.devices.fd import MideaFDDevice

from homeassistant.components.humidifier import (
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityDescription,
    HumidifierEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MideaConfigEntry, MideaEntity, midea_api_call

PARALLEL_UPDATES = 0

type MideaHumidifierDevice = MideaA1Device | MideaFDDevice


@dataclass(kw_only=True, frozen=True)
class MideaHumidifierEntityDescription(HumidifierEntityDescription):
    """Description for a Midea humidifier entity."""

    models: list[DeviceType]


HUMIDIFIERS: list[MideaHumidifierEntityDescription] = [
    MideaHumidifierEntityDescription(
        key="humidifier",
        models=[DeviceType.A1],
        device_class=HumidifierDeviceClass.DEHUMIDIFIER,
    ),
    MideaHumidifierEntityDescription(
        key="humidifier",
        models=[DeviceType.FD],
        device_class=HumidifierDeviceClass.HUMIDIFIER,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MideaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up humidifiers for device."""
    device = config_entry.runtime_data

    async_add_entities(
        MideaHumidifier(device, description)
        for description in HUMIDIFIERS
        if device.device_type in description.models
    )


class MideaHumidifier(MideaEntity, HumidifierEntity):
    """Represent a Midea humidifier."""

    _device: MideaHumidifierDevice
    entity_description: MideaHumidifierEntityDescription

    _attr_min_humidity: float = 35
    _attr_max_humidity: float = 85
    _attr_supported_features = HumidifierEntityFeature.MODES

    def _float_attribute(self, attr: str) -> float | None:
        """Return a device attribute as float, if convertible."""
        value = self._device.get_attribute(attr)
        if not isinstance(value, (int, float, str)):
            return None
        return float(value)

    @property
    @override
    def current_humidity(self) -> float | None:
        """Midea Humidifier current humidity."""
        return self._float_attribute("current_humidity")

    @property
    @override
    def target_humidity(self) -> float | None:
        """Midea Humidifier target humidity."""
        return self._float_attribute("target_humidity")

    @property
    @override
    def mode(self) -> str | None:
        """Midea Humidifier mode."""
        mode = self._device.get_attribute("mode")
        if not isinstance(mode, str):
            return None
        return mode

    @property
    @override
    def available_modes(self) -> list[str]:
        """Midea Humidifier available modes."""
        return self._device.modes

    @property
    @override
    def is_on(self) -> bool | None:
        """Midea Humidifier is on."""
        power = self._device.get_attribute("power")
        if not isinstance(power, bool):
            return None
        return power

    @override
    def set_humidity(self, humidity: int) -> None:
        """Midea Humidifier set humidity."""
        with midea_api_call():
            self._device.set_attribute(attr="target_humidity", value=humidity)

    @override
    def set_mode(self, mode: str) -> None:
        """Midea Humidifier set mode."""
        with midea_api_call():
            self._device.set_attribute(attr="mode", value=mode)

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Midea Humidifier turn on."""
        with midea_api_call():
            self._device.set_attribute(attr="power", value=True)

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Midea Humidifier turn off."""
        with midea_api_call():
            self._device.set_attribute(attr="power", value=False)
