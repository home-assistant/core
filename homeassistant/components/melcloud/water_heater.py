"""Platform for water_heater integration."""
from __future__ import annotations

from pymelcloud import DEVICE_TYPE_ATW, AtwDevice
from pymelcloud.atw_device import (
    PROPERTY_OPERATION_MODE,
    PROPERTY_TARGET_TANK_TEMPERATURE,
)
from pymelcloud.device import PROPERTY_POWER

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, MelCloudDevice
from .const import ATTR_STATUS


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up MelCloud device climate based on config_entry."""
    mel_devices = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            AtwWaterHeater(mel_device, mel_device.device)
            for mel_device in mel_devices[DEVICE_TYPE_ATW]
        ],
        True,
    )


class AtwWaterHeater(WaterHeaterEntity):
    """Air-to-Water water heater."""

    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )

    def __init__(self, api: MelCloudDevice, device: AtwDevice) -> None:
        """Initialize water heater device."""
        self._api = api
        self._device = device
        self._name = device.name

    async def async_update(self):
        """Update state from MELCloud."""
        await self._api.async_update()

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return f"{self._api.device.serial}"

    @property
    def name(self):
        """Return the display name of this entity."""
        return self._name

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._api.device_info

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self._device.set({PROPERTY_POWER: True})

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self._device.set({PROPERTY_POWER: False})

    @property
    def extra_state_attributes(self):
        """Return the optional state attributes with device specific additions."""
        data = {ATTR_STATUS: self._device.status}
        return data

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def current_operation(self) -> str | None:
        """Return current operation as reported by pymelcloud."""
        return self._device.operation_mode

    @property
    def operation_list(self) -> list[str]:
        """Return the list of available operation modes as reported by pymelcloud."""
        return self._device.operation_modes

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.tank_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._device.target_tank_temperature

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        await self._device.set(
            {
                PROPERTY_TARGET_TANK_TEMPERATURE: kwargs.get(
                    "temperature", self.target_temperature
                )
            }
        )

    async def async_set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        await self._device.set({PROPERTY_OPERATION_MODE: operation_mode})

    @property
    def min_temp(self) -> float | None:
        """Return the minimum temperature."""
        return self._device.target_tank_temperature_min

    @property
    def max_temp(self) -> float | None:
        """Return the maximum temperature."""
        return self._device.target_tank_temperature_max
