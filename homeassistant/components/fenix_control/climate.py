"""Climate platform for the FENIX Control integration."""

import dataclasses
from typing import Any, override

from pyfenixcontrol import Device, FenixControlError, HvacState, PresetMode

from homeassistant.components.climate import (
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOME,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import FenixControlConfigEntry, FenixControlCoordinator
from .entity import FenixControlEntity

# Commands go to the cloud; send them one at a time
PARALLEL_UPDATES = 1

HVAC_MODE_TO_PRESET_MODE: dict[HVACMode, PresetMode] = {
    HVACMode.OFF: PresetMode.OFF,
    HVACMode.AUTO: PresetMode.PROGRAM,
    HVACMode.HEAT: PresetMode.MANUAL,
}

PRESET_TO_PRESET_MODE: dict[str, PresetMode] = {
    PRESET_HOME: PresetMode.PROGRAM,
    PRESET_ECO: PresetMode.DEFROST,
    PRESET_COMFORT: PresetMode.BOOST,
}
PRESET_MODE_TO_PRESET: dict[int, str] = {
    mode: preset for preset, mode in PRESET_TO_PRESET_MODE.items()
}

HVAC_STATE_TO_HVAC_ACTION: dict[HvacState, HVACAction] = {
    HvacState.IDLE: HVACAction.IDLE,
    HvacState.HEATING: HVACAction.HEATING,
    HvacState.OFF: HVACAction.OFF,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FenixControlConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up FENIX Control climate entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        FenixControlClimate(coordinator, device_id)
        for device_id in coordinator.data.devices
    )


class FenixControlClimate(FenixControlEntity, ClimateEntity):
    """A FENIX TFT Wi-Fi thermostat."""

    _attr_name = None
    _attr_hvac_modes = list(HVAC_MODE_TO_PRESET_MODE)
    _attr_preset_modes = list(PRESET_TO_PRESET_MODE)
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 5.0
    _attr_max_temp = 35.0
    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator: FenixControlCoordinator, device_id: str) -> None:
        """Initialize the thermostat."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = device_id

    @property
    @override
    def native_current_temperature(self) -> float | None:
        """Return the room temperature."""
        return self.device.room_temperature

    @property
    @override
    def native_target_temperature(self) -> float | None:
        """Return the target temperature used outside a holiday."""
        return self.device.target_temperature

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Return the HVAC mode; holiday, defrost and boost follow the program."""
        match self.device.preset_mode:
            case PresetMode.OFF:
                return HVACMode.OFF
            case PresetMode.MANUAL:
                return HVACMode.HEAT
        return HVACMode.AUTO

    @property
    @override
    def hvac_modes(self) -> list[HVACMode]:
        """Return the selectable HVAC modes; none can be chosen during a holiday."""
        if self.device.holiday_active:
            return [self.hvac_mode]
        return self._attr_hvac_modes

    @property
    @override
    def hvac_action(self) -> HVACAction | None:
        """Return whether the thermostat is heating."""
        # During a holiday the heating state field carries the holiday mode
        if self.device.holiday_active or self.device.hvac_state is None:
            return None
        try:
            return HVAC_STATE_TO_HVAC_ACTION[HvacState(self.device.hvac_state)]
        except ValueError:
            return None

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return the preset, if the thermostat is in one."""
        if self.device.preset_mode is None:
            return None
        return PRESET_MODE_TO_PRESET.get(self.device.preset_mode)

    @property
    @override
    def supported_features(self) -> ClimateEntityFeature:
        """Return the features available in the current mode."""
        if self.device.holiday_active:
            # A holiday is set for the whole installation and locks the controls
            return ClimateEntityFeature(0)
        if self.device.preset_mode == PresetMode.MANUAL:
            return (
                ClimateEntityFeature.TARGET_TEMPERATURE
                | ClimateEntityFeature.PRESET_MODE
            )
        return ClimateEntityFeature.PRESET_MODE

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature; this switches the thermostat to manual."""
        temperature: float = kwargs[ATTR_TEMPERATURE]
        try:
            await self.coordinator.client.set_target_temperature(
                self._device_id, temperature
            )
        except FenixControlError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_temperature_failed",
            ) from err
        self._update_device(
            target_temperature=temperature, preset_mode=int(PresetMode.MANUAL)
        )

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        # A holiday locks the controls; Home Assistant still lets the current
        # mode be selected again
        if self.device.holiday_active:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="holiday_active"
            )
        await self._async_set_preset_mode(
            HVAC_MODE_TO_PRESET_MODE[hvac_mode], "set_hvac_mode_failed"
        )

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset."""
        await self._async_set_preset_mode(
            PRESET_TO_PRESET_MODE[preset_mode], "set_preset_mode_failed"
        )

    async def _async_set_preset_mode(
        self, mode: PresetMode, translation_key: str
    ) -> None:
        try:
            await self.coordinator.client.set_preset_mode(self._device_id, mode)
        except FenixControlError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key=translation_key
            ) from err
        self._update_device(preset_mode=int(mode))

    def _update_device(self, **changes: Any) -> None:
        """Show the commanded state until the next poll confirms it."""
        # The cloud reports a change only after the thermostat has applied it,
        # so an immediate refresh would show the old state
        device: Device = dataclasses.replace(self.device, **changes)
        data = self.coordinator.data
        self.coordinator.async_set_updated_data(
            dataclasses.replace(data, devices={**data.devices, self._device_id: device})
        )
