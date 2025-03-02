"""EHEIM Digital climate."""

from typing import Any

from eheimdigital.device import EheimDigitalDevice
from eheimdigital.heater import EheimDigitalHeater
from eheimdigital.types import EheimDigitalClientError, HeaterMode, HeaterUnit

from homeassistant.components.climate import (
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import HEATER_BIO_MODE, HEATER_PRESET_TO_HEATER_MODE, HEATER_SMART_MODE
from .coordinator import EheimDigitalConfigEntry, EheimDigitalUpdateCoordinator
from .entity import EheimDigitalEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EheimDigitalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the callbacks for the coordinator so climate entities can be added as devices are found."""
    coordinator = entry.runtime_data

    def async_setup_device_entities(
        device_address: dict[str, EheimDigitalDevice],
    ) -> None:
        """Set up the climate entities for one or multiple devices."""
        entities: list[EheimDigitalHeaterClimate] = []
        for device in device_address.values():
            if isinstance(device, EheimDigitalHeater):
                entities.append(EheimDigitalHeaterClimate(coordinator, device))
                coordinator.known_devices.add(device.mac_address)

        async_add_entities(entities)

    coordinator.add_platform_callback(async_setup_device_entities)

    async_setup_device_entities(coordinator.hub.devices)


class EheimDigitalHeaterClimate(EheimDigitalEntity[EheimDigitalHeater], ClimateEntity):
    """Represent an EHEIM Digital heater."""

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO]
    _attr_hvac_mode = HVACMode.OFF
    _attr_precision = PRECISION_TENTHS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.PRESET_MODE
    )
    _attr_target_temperature_step = PRECISION_HALVES
    _attr_preset_modes = [PRESET_NONE, HEATER_BIO_MODE, HEATER_SMART_MODE]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_preset_mode = PRESET_NONE
    _attr_translation_key = "heater"
    _attr_name = None

    def __init__(
        self, coordinator: EheimDigitalUpdateCoordinator, device: EheimDigitalHeater
    ) -> None:
        """Initialize an EHEIM Digital thermocontrol climate entity."""
        super().__init__(coordinator, device)
        self._attr_unique_id = self._device_address
        self._async_update_attrs()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        try:
            if preset_mode in HEATER_PRESET_TO_HEATER_MODE:
                await self._device.set_operation_mode(
                    HEATER_PRESET_TO_HEATER_MODE[preset_mode]
                )
        except EheimDigitalClientError as err:
            raise HomeAssistantError from err

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new temperature."""
        try:
            if ATTR_TEMPERATURE in kwargs:
                await self._device.set_target_temperature(kwargs[ATTR_TEMPERATURE])
        except EheimDigitalClientError as err:
            raise HomeAssistantError from err

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the heating mode."""
        try:
            match hvac_mode:
                case HVACMode.OFF:
                    await self._device.set_active(active=False)
                case HVACMode.AUTO:
                    await self._device.set_active(active=True)
        except EheimDigitalClientError as err:
            raise HomeAssistantError from err

    def _async_update_attrs(self) -> None:
        if self._device.temperature_unit == HeaterUnit.CELSIUS:
            self._attr_min_temp = 18
            self._attr_max_temp = 32
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        elif self._device.temperature_unit == HeaterUnit.FAHRENHEIT:
            self._attr_min_temp = 64
            self._attr_max_temp = 90
            self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT

        self._attr_current_temperature = self._device.current_temperature
        self._attr_target_temperature = self._device.target_temperature

        if self._device.is_heating:
            self._attr_hvac_action = HVACAction.HEATING
            self._attr_hvac_mode = HVACMode.AUTO
        elif self._device.is_active:
            self._attr_hvac_action = HVACAction.IDLE
            self._attr_hvac_mode = HVACMode.AUTO
        else:
            self._attr_hvac_action = HVACAction.OFF
            self._attr_hvac_mode = HVACMode.OFF

        match self._device.operation_mode:
            case HeaterMode.MANUAL:
                self._attr_preset_mode = PRESET_NONE
            case HeaterMode.BIO:
                self._attr_preset_mode = HEATER_BIO_MODE
            case HeaterMode.SMART:
                self._attr_preset_mode = HEATER_SMART_MODE
