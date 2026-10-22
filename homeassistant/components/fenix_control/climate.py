"""Climate platform for the FENIX Control integration."""

import dataclasses
from typing import Any, override

from pyfenixcontrol import Device, FenixControlError, HvacState, PresetMode

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_HOME,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
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
    PRESET_AWAY: PresetMode.DEFROST,
    PRESET_BOOST: PresetMode.BOOST,
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
        self._last_on_mode = HVACMode.AUTO
        self._remember_on_mode()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Track the last HVAC mode in which the thermostat was on."""
        super()._handle_coordinator_update()
        self._remember_on_mode()

    def _remember_on_mode(self) -> None:
        if (mode := self.hvac_mode) not in (None, HVACMode.OFF):
            self._last_on_mode = mode

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
    def hvac_mode(self) -> HVACMode | None:
        """Return the HVAC mode; holiday, defrost and boost follow the program."""
        match self.device.preset_mode:
            case PresetMode.OFF:
                return HVACMode.OFF
            case PresetMode.MANUAL:
                return HVACMode.HEAT
            case (
                PresetMode.PROGRAM
                | PresetMode.HOLIDAYS
                | PresetMode.DEFROST
                | PresetMode.BOOST
            ):
                return HVACMode.AUTO
        return None

    @property
    @override
    def hvac_modes(self) -> list[HVACMode]:
        """Return the selectable HVAC modes; none can be chosen during a holiday."""
        if self.device.holiday_active:
            return [mode] if (mode := self.hvac_mode) is not None else []
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
        features = (
            ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        if self.device.preset_mode == PresetMode.MANUAL:
            return features | ClimateEntityFeature.TARGET_TEMPERATURE
        return features

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature; this switches the thermostat to manual."""
        temperature: float = kwargs[ATTR_TEMPERATURE]
        hvac_mode: HVACMode | None = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode is not None and hvac_mode not in self.hvac_modes:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_hvac_mode",
                translation_placeholders={"hvac_mode": hvac_mode},
            )
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
        # The temperature command already selects manual (heat) mode
        if hvac_mode is not None and hvac_mode != HVACMode.HEAT:
            await self.async_set_hvac_mode(hvac_mode)

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
    async def async_turn_on(self) -> None:
        """Turn on in the last used HVAC mode, the weekly program if unknown."""
        await self.async_set_hvac_mode(self._last_on_mode)

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
        # Keep the poll schedule; frequent commands must not postpone polling
        self.coordinator.data = dataclasses.replace(
            data, devices={**data.devices, self._device_id: device}
        )
        self.coordinator.async_update_listeners()
