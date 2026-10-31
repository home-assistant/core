"""Number platform for the BLUETTI Modbus integration."""

from typing import override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BluettiModbusConfigEntry
from .entity import BluettiModbusSettingEntity

# The device takes one Modbus request at a time.
PARALLEL_UPDATES = 1

# The bounds are the ones the library accepts for each register.
NUMBER_DESCRIPTIONS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="b_soc_low",
        translation_key="battery_soc_low",
        native_unit_of_measurement=PERCENTAGE,
        device_class=NumberDeviceClass.BATTERY,
        native_min_value=5,
        native_max_value=90,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    NumberEntityDescription(
        key="b_soc_high",
        translation_key="battery_soc_high",
        native_unit_of_measurement=PERCENTAGE,
        device_class=NumberDeviceClass.BATTERY,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BluettiModbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BLUETTI Modbus numbers from a config entry."""
    async_add_entities(
        BluettiModbusNumber(entry=entry, description=description)
        for description in NUMBER_DESCRIPTIONS
    )


class BluettiModbusNumber(BluettiModbusSettingEntity, NumberEntity):
    """Defines a BLUETTI Modbus number."""

    def __init__(
        self, *, entry: BluettiModbusConfigEntry, description: NumberEntityDescription
    ) -> None:
        """Initialize a BLUETTI Modbus number."""
        super().__init__(entry=entry, field_name=description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> int:
        """Return the setting's value."""
        return int(self.coordinator.data[self._field_name])

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Write a new value to the device."""
        await self._async_write(int(value))
