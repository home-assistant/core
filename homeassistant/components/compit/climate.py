"""Module contains the CompitClimate class for controlling climate entities."""

from typing import Any

from compit_inext_api import Device, Parameter

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANURFACER_NAME
from .coordinator import CompitDataUpdateCoordinator

type CompitConfigEntry = ConfigEntry[CompitDataUpdateCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CompitConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Set up the CompitClimate platform from a config entry."""

    coordinator: CompitDataUpdateCoordinator = entry.runtime_data

    async_add_devices(
        [
            CompitClimate(
                coordinator,
                device,
                device_definition.parameters,
                device_definition.name,
            )
            for gates in coordinator.gates
            for device in gates.devices
            if (
                device_definition := next(
                    (
                        definition
                        for definition in coordinator.device_definitions.devices
                        if definition.code == device.type
                    ),
                    None,
                )
            )
            is not None
            if (device_definition.device_class == 10)
        ]
    )


class CompitClimate(CoordinatorEntity[CompitDataUpdateCoordinator], ClimateEntity):
    """Representation of a Compit climate device."""

    def __init__(
        self,
        coordinator: CompitDataUpdateCoordinator,
        device: Device,
        parameters: list[Parameter],
        device_name: str,
    ) -> None:
        """Initialize the climate device."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_unique_id = f"{device.label}_{device.id}"
        self._attr_name = device.label
        self._attr_has_entity_name = True
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self.parameters = {
            parameter.parameter_code: parameter for parameter in parameters
        }
        self.device = device
        self.available_presets: Parameter | None = self.parameters.get(
            "__trybpracytermostatu"
        )
        self.available_fan_modes: Parameter | None = self.parameters.get("__trybaero")
        self.available_hvac_modes: Parameter | None = self.parameters.get(
            "__trybpracyinstalacji"
        )
        self.device_name = device_name
        self._temperature: float | None = None
        self._preset_mode: int | None = None
        self._fan_mode: int | None = None
        self._hvac_mode: HVACMode | None = None
        self.set_initial_values()

    def set_initial_values(self) -> None:
        """Set initial values for the climate device."""

        preset_mode = self.coordinator.data[self.device.id].state.get_parameter_value(
            "__trybpracytermostatu"
        )
        if preset_mode and self.available_presets and self.available_presets.details:
            preset = next(
                (
                    item
                    for item in self.available_presets.details
                    if item is not None and item.state == preset_mode.value
                ),
                None,
            )
            self._preset_mode = preset.state if preset is not None else None
        else:
            self._preset_mode = None
        fan_mode = self.coordinator.data[self.device.id].state.get_parameter_value(
            "__trybaero"
        )
        if fan_mode and self.available_fan_modes and self.available_fan_modes.details:
            fan = next(
                (
                    item
                    for item in self.available_fan_modes.details
                    if item is not None and item.state == fan_mode.value
                ),
                None,
            )
            self._fan_mode = fan.state if fan is not None else None
        else:
            self._fan_mode = None

        hvac_mode = self.coordinator.data[self.device.id].state.get_parameter_value(
            "__trybpracyinstalacji"
        )
        if hvac_mode is not None:
            if hvac_mode.value == 0:
                self._hvac_mode = HVACMode.HEAT
            if hvac_mode.value == 1:
                self._hvac_mode = HVACMode.OFF
            if hvac_mode.value == 2:
                self._hvac_mode = HVACMode.COOL
        else:
            self._hvac_mode = None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information about this climate device."""

        return {
            "identifiers": {(DOMAIN, str(self.device.id))},
            "name": self.device.label,
            "manufacturer": MANURFACER_NAME,
            "model": self.device_name,
            "sw_version": "1.0",
        }

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        value = self.coordinator.data[self.device.id].state.get_parameter_value(
            "__tpokojowa"
        )
        if value is None:
            return None
        return float(value.value) if value is not None else None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        value = self.coordinator.data[self.device.id].state.get_parameter_value(
            "__tpokzadana"
        )
        if value is None:
            return None
        return float(value.value) if value is not None else None

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
        )

    @property
    def preset_modes(self) -> list[str] | None:
        """Return the available preset modes."""
        if self.available_presets is None or self.available_presets.details is None:
            return []
        return [
            item.description
            for item in self.available_presets.details
            if item is not None
        ]

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the available fan modes."""
        if self.available_fan_modes is None or self.available_fan_modes.details is None:
            return []
        return [
            item.description
            for item in self.available_fan_modes.details
            if item is not None
        ]

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the available HVAC modes."""
        return [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if (
            self._preset_mode is None
            or self.available_presets is None
            or self.available_presets.details is None
        ):
            return None

        val = next(
            (
                item
                for item in self.available_presets.details
                if item is not None and item.state == self._preset_mode
            ),
            None,
        )
        if val is None:
            return None
        return str(val.description)

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        if (
            self._fan_mode is None
            or self.available_fan_modes is None
            or self.available_fan_modes.details is None
        ):
            return None

        val = next(
            (
                item
                for item in self.available_fan_modes.details
                if item is not None and item.state == self._fan_mode
            ),
            None,
        )
        if val is None:
            return None
        return str(val.description)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        return self._hvac_mode

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get("temperature")
        if temp is None:
            return
        self._temperature = temp
        await self.async_call_api("__tempzadpracareczna", temp)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode."""
        value = 0
        if hvac_mode == HVACMode.HEAT:
            value = 0
        elif hvac_mode == HVACMode.OFF:
            value = 1
        elif hvac_mode == HVACMode.COOL:
            value = 2
        self._hvac_mode = hvac_mode
        await self.async_call_api("__trybpracyinstalacji", value)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        if self.available_presets is None or self.available_presets.details is None:
            return
        value = next(
            (
                item
                for item in self.available_presets.details
                if item is not None and item.description == preset_mode
            ),
            None,
        )
        if value is None:
            return
        self._preset_mode = value.state
        await self.async_call_api("__trybpracytermostatu", value.state)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if self.available_fan_modes is None or self.available_fan_modes.details is None:
            return
        value = next(
            (
                item
                for item in self.available_fan_modes.details
                if item is not None and item.description == fan_mode
            ),
            None,
        )
        if value is None:
            return
        self._fan_mode = value.state
        await self.async_call_api("__trybaero", value.state)

    async def async_call_api(self, parameter: str, value: int) -> None:
        """Call the API to set a parameter to a new value."""

        if (
            await self.coordinator.api.update_device_parameter(
                self.device.id, parameter, value
            )
            is not False
        ):
            await self.coordinator.async_request_refresh()
            self.async_write_ha_state()
