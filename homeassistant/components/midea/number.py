"""Number for Midea."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast, override

from midealocal.const import DeviceType
from midealocal.device import MideaDevice
from midealocal.devices.c2 import MideaC2Device

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MideaConfigEntry, MideaEntity, midea_api_call

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class MideaNumberEntityDescription(NumberEntityDescription):
    """Description for a Midea number entity."""

    models: list[DeviceType]
    max_value_fn: Callable[[MideaDevice], float | None] | None = None


NUMBERS: list[MideaNumberEntityDescription] = [
    MideaNumberEntityDescription(
        key="dry_level",
        translation_key="dry_level",
        models=[DeviceType.C2],
        native_min_value=0,
        max_value_fn=lambda device: cast(MideaC2Device, device).max_dry_level,
        native_step=1,
    ),
    MideaNumberEntityDescription(
        key="water_temp_level",
        translation_key="water_temp_level",
        models=[DeviceType.C2],
        native_min_value=0,
        max_value_fn=lambda device: cast(MideaC2Device, device).max_water_temp_level,
        native_step=1,
    ),
    MideaNumberEntityDescription(
        key="seat_temp_level",
        translation_key="seat_temp_level",
        models=[DeviceType.C2],
        native_min_value=0,
        max_value_fn=lambda device: cast(MideaC2Device, device).max_seat_temp_level,
        native_step=1,
    ),
    MideaNumberEntityDescription(
        key="vacation_days",
        translation_key="vacation_days",
        models=[DeviceType.CD],
        device_class=NumberDeviceClass.DURATION,
        native_min_value=1,
        native_max_value=360,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.DAYS,
    ),
    MideaNumberEntityDescription(
        key="water_hardness",
        translation_key="water_hardness",
        models=[DeviceType.ED],
        native_min_value=0,
        native_max_value=65535,
        native_step=1,
    ),
    MideaNumberEntityDescription(
        key="flushing_days",
        translation_key="flushing_days",
        models=[DeviceType.ED],
        device_class=NumberDeviceClass.DURATION,
        native_min_value=0,
        native_max_value=99,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.DAYS,
    ),
    MideaNumberEntityDescription(
        key="leak_water_protection_value",
        translation_key="leak_water_protection_value",
        models=[DeviceType.ED],
        device_class=NumberDeviceClass.VOLUME,
        native_min_value=0,
        native_max_value=2550,
        native_step=50,
        native_unit_of_measurement=UnitOfVolume.LITERS,
    ),
    MideaNumberEntityDescription(
        key="heating_level",
        translation_key="heating_level",
        models=[DeviceType.FB],
        native_min_value=1,
        native_max_value=10,
        native_step=1,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MideaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up numbers for device."""
    device = config_entry.runtime_data

    async_add_entities(
        MideaNumber(device, description)
        for description in NUMBERS
        if device.device_type in description.models
        # None means the model doesn't support this attribute at all,
        # unlike select.py's key-presence check.
        and device.attributes.get(description.key) is not None
    )


class MideaNumber(MideaEntity, NumberEntity):
    """Represent a Midea number."""

    entity_description: MideaNumberEntityDescription

    @property
    @override
    def native_max_value(self) -> float:
        """Return the maximum value, reading it off the device if dynamic."""
        if self.entity_description.max_value_fn is not None:
            value = self.entity_description.max_value_fn(self._device)
            if value is not None:
                return value
        return super().native_max_value

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value."""
        value = self._device.get_attribute(self.entity_description.key)
        if not isinstance(value, (int, float)):
            return None
        return float(value)

    @override
    def set_native_value(self, value: float) -> None:
        """Set the value."""
        step = self.step
        value = round(value / step) * step
        with midea_api_call():
            self._device.set_attribute(
                attr=self.entity_description.key, value=round(value)
            )
