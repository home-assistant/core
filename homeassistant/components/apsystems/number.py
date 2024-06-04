"""The output limit which can be set in the APsystems local API integration."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from . import ApSystemsConfigEntry, ApSystemsData
from .entity import ApSystemsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ApSystemsConfigEntry,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    config = config_entry.runtime_data

    add_entities([ApSystemsMaxOutputNumber(config)])


class ApSystemsMaxOutputNumber(ApSystemsEntity, NumberEntity):
    """Base sensor to be used with description."""

    _attr_native_max_value = 800
    _attr_native_min_value = 30
    _attr_native_step = 1
    _attr_device_class = NumberDeviceClass.POWER
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(
        self,
        data: ApSystemsData,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(data)
        self._api = data.api
        self._attr_unique_id = f"{data.device_id}_output_limit"

    async def async_update(self) -> None:
        """Set the state with the value fetched from the inverter."""
        self._attr_native_value = float(await self._api.get_max_power())

    async def async_set_native_value(self, value: float) -> None:
        """Set the desired output power."""
        value_as_int = int(value)
        await self._api.set_max_power(value_as_int)
        self._attr_native_value = value
