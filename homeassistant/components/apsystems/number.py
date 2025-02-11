"""The output limit which can be set in the APsystems local API integration."""

from __future__ import annotations

from aiohttp import ClientConnectorError

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from .coordinator import ApSystemsConfigEntry, ApSystemsData
from .entity import ApSystemsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ApSystemsConfigEntry,
    add_entities: AddConfigEntryEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""

    add_entities([ApSystemsMaxOutputNumber(config_entry.runtime_data)], True)


class ApSystemsMaxOutputNumber(ApSystemsEntity, NumberEntity):
    """Base sensor to be used with description."""

    _attr_native_step = 1
    _attr_device_class = NumberDeviceClass.POWER
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_translation_key = "max_output"

    def __init__(
        self,
        data: ApSystemsData,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(data)
        self._api = data.coordinator.api
        self._attr_unique_id = f"{data.device_id}_output_limit"
        self._attr_native_max_value = data.coordinator.api.max_power
        self._attr_native_min_value = data.coordinator.api.min_power

    async def async_update(self) -> None:
        """Set the state with the value fetched from the inverter."""
        try:
            status = await self._api.get_max_power()
        except (TimeoutError, ClientConnectorError):
            self._attr_available = False
        else:
            self._attr_available = True
            self._attr_native_value = status

    async def async_set_native_value(self, value: float) -> None:
        """Set the desired output power."""
        self._attr_native_value = await self._api.set_max_power(int(value))
