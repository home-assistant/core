"""The input to set max output for APsystems local API integration."""

from __future__ import annotations

from aiohttp import client_exceptions
from APsystemsEZ1 import APsystemsEZ1M
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.number import (
    PLATFORM_SCHEMA,
    NumberDeviceClass,
    NumberEntity,
)
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_NAME, default="solar"): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    api = APsystemsEZ1M(ip_address=config[CONF_IP_ADDRESS])

    numbers = [
        MaxPower(
            api,
            device_name=config[CONF_NAME],
            sensor_name="Max Output Power",
            sensor_id="max_output_power",
        )
    ]

    add_entities(numbers, True)


class MaxPower(NumberEntity):
    """Represents Max power of the inverter whitch the user can set."""

    _attr_device_class = NumberDeviceClass.POWER
    _attr_available = False
    _attr_native_max_value = 800
    _attr_native_min_value = 30
    _attr_native_step = 1

    def __init__(
        self, api: APsystemsEZ1M, device_name: str, sensor_name: str, sensor_id: str
    ) -> None:
        """Initialize the sensor."""
        self._api = api
        self._state = None
        self._device_name = device_name
        self._name = sensor_name
        self._sensor_id = sensor_id

    async def async_update(self) -> None:
        """Update the state."""
        try:
            self._state = await self._api.get_max_power()
            self._attr_available = True
        except (TimeoutError, client_exceptions.ClientConnectionError):
            self._attr_available = False

    @property  # type: ignore[misc]
    def state(self) -> int | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def unique_id(self) -> str | None:
        """Get the unique input id."""
        return f"apsystemsapi_{self._device_name}_{self._sensor_id}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"APsystems {self._device_name} {self._name}"

    async def async_set_native_value(self, value: float) -> None:
        """Set the new value."""
        try:
            await self._api.set_max_power(int(value))
            self._attr_available = True
        except (TimeoutError, client_exceptions.ClientConnectionError):
            self._attr_available = False
        await self.async_update()

    @property
    def device_info(self) -> DeviceInfo:
        """Get the device info."""
        return DeviceInfo(
            identifiers={("apsystemsapi_local", self._device_name)},
            name=self._device_name,
            manufacturer="APsystems",
            model="EZ1-M",
        )
