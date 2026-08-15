"""Number for Midea."""

from dataclasses import dataclass
from typing import override

from midealocal.const import DeviceType

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MideaConfigEntry, MideaEntity, midea_api_call

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class MideaNumberEntityDescription(NumberEntityDescription):
    """Description for a Midea number entity."""

    models: list[DeviceType]
    max_value_attribute: str | None = None
    """Device property name for a dynamic max value, overriding native_max_value."""


NUMBERS: list[MideaNumberEntityDescription] = [
    MideaNumberEntityDescription(
        key="dry_level",
        translation_key="dry_level",
        models=[DeviceType.C2],
        native_min_value=0,
        max_value_attribute="max_dry_level",
        native_step=1,
    ),
    MideaNumberEntityDescription(
        key="water_temp_level",
        translation_key="water_temp_level",
        models=[DeviceType.C2],
        native_min_value=0,
        max_value_attribute="max_water_temp_level",
        native_step=1,
    ),
    MideaNumberEntityDescription(
        key="seat_temp_level",
        translation_key="seat_temp_level",
        models=[DeviceType.C2],
        native_min_value=0,
        max_value_attribute="max_seat_temp_level",
        native_step=1,
    ),
    MideaNumberEntityDescription(
        key="vacation_days",
        translation_key="vacation_days",
        models=[DeviceType.CD],
        native_min_value=1,
        native_max_value=360,
        native_step=1,
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
        native_min_value=0,
        native_max_value=99,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.DAYS,
    ),
    MideaNumberEntityDescription(
        key="leak_water_protection_value",
        translation_key="leak_water_protection_value",
        models=[DeviceType.ED],
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
        and device.attributes.get(description.key) is not None
    )


class MideaNumber(MideaEntity, NumberEntity):
    """Represent a Midea number."""

    entity_description: MideaNumberEntityDescription

    @property
    @override
    def native_max_value(self) -> float:
        """Return the maximum value, reading it off the device if dynamic."""
        if self.entity_description.max_value_attribute is not None:
            return getattr(self._device, self.entity_description.max_value_attribute)
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
        with midea_api_call():
            self._device.set_attribute(
                attr=self.entity_description.key, value=round(value)
            )
