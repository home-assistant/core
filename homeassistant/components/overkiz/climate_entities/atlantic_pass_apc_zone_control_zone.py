"""Support for Atlantic Pass APC Heating Control."""
from __future__ import annotations

from asyncio import sleep
from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.climate import PRESET_NONE, HVACMode
from homeassistant.const import ATTR_TEMPERATURE

from ..coordinator import OverkizDataUpdateCoordinator
from .atlantic_pass_apc_heating_zone import AtlanticPassAPCHeatingZone
from .atlantic_pass_apc_zone_control import OVERKIZ_TO_HVAC_MODE

PRESET_SCHEDULE = "schedule"
PRESET_MANUAL = "manual"

OVERKIZ_MODE_TO_PRESET_MODES: dict[str, str] = {
    OverkizCommandParam.MANU: PRESET_MANUAL,
    OverkizCommandParam.INTERNAL_SCHEDULING: PRESET_SCHEDULE,
}

PRESET_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_MODE_TO_PRESET_MODES.items()}

TEMPERATURE_ZONECONTROL_DEVICE_INDEX = 1


# Those device depends on a main probe that choose the operating mode (heating, cooling, ...)
class AtlanticPassAPCZoneControlZone(AtlanticPassAPCHeatingZone):
    """Representation of Atlantic Pass APC Heating And Cooling Zone Control."""

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)

        # There is less supported functions, because they depend on the ZoneControl.
        if not self.is_using_derogated_temperature_fallback:
            # Modes are not configurable, they will follow current HVAC Mode of Zone Control.
            self._attr_hvac_modes = []

            # Those are available and tested presets on Shogun.
            self._attr_preset_modes = [*PRESET_MODES_TO_OVERKIZ]

        # Those APC Heating and Cooling probes depends on the zone control device (main probe).
        # Only the base device (#1) can be used to get/set some states.
        # Like to retrieve and set the current operating mode (heating, cooling, drying, off).
        self.zone_control_device = self.executor.linked_device(
            TEMPERATURE_ZONECONTROL_DEVICE_INDEX
        )

    @property
    def is_using_derogated_temperature_fallback(self) -> bool:
        """Check if the device behave like the Pass APC Heating Zone."""

        return self.executor.has_command(
            OverkizCommand.SET_DEROGATED_TARGET_TEMPERATURE
        )

    @property
    def zone_control_hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool, dry, off mode."""

        if (
            state := self.zone_control_device.states[
                OverkizState.IO_PASS_APC_OPERATING_MODE
            ]
        ) is not None and (value := state.value_as_str) is not None:
            return OVERKIZ_TO_HVAC_MODE[value]
        return HVACMode.OFF

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool, dry, off mode."""

        if self.is_using_derogated_temperature_fallback:
            return super().hvac_mode

        zone_control_hvac_mode = self.zone_control_hvac_mode

        # Should be same, because either thermostat or this integration change both.
        on_off_state = cast(
            str,
            self.executor.select_state(
                OverkizState.CORE_COOLING_ON_OFF
                if zone_control_hvac_mode == HVACMode.COOL
                else OverkizState.CORE_HEATING_ON_OFF
            ),
        )

        # Device is Stopped, it means the air flux is flowing but its venting door is closed.
        if on_off_state == OverkizCommandParam.OFF:
            hvac_mode = HVACMode.OFF
        else:
            hvac_mode = zone_control_hvac_mode

        # It helps keep it consistent with the Zone Control, within the interface.
        if self._attr_hvac_modes != [zone_control_hvac_mode, HVACMode.OFF]:
            self._attr_hvac_modes = [zone_control_hvac_mode, HVACMode.OFF]
            self.async_write_ha_state()

        return hvac_mode

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""

        if self.is_using_derogated_temperature_fallback:
            return await super().async_set_hvac_mode(hvac_mode)

        # They are mainly managed by the Zone Control device
        # However, it make sense to map the OFF Mode to the Overkiz STOP Preset

        if hvac_mode == HVACMode.OFF:
            await self.executor.async_execute_command(
                OverkizCommand.SET_COOLING_ON_OFF,
                OverkizCommandParam.OFF,
            )
            await self.executor.async_execute_command(
                OverkizCommand.SET_HEATING_ON_OFF,
                OverkizCommandParam.OFF,
            )
        else:
            await self.executor.async_execute_command(
                OverkizCommand.SET_COOLING_ON_OFF,
                OverkizCommandParam.ON,
            )
            await self.executor.async_execute_command(
                OverkizCommand.SET_HEATING_ON_OFF,
                OverkizCommandParam.ON,
            )

        await self.async_refresh_modes()

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode, e.g., schedule, manual."""

        if self.is_using_derogated_temperature_fallback:
            return super().preset_mode

        mode = OVERKIZ_MODE_TO_PRESET_MODES[
            cast(
                str,
                self.executor.select_state(
                    OverkizState.IO_PASS_APC_COOLING_MODE
                    if self.zone_control_hvac_mode == HVACMode.COOL
                    else OverkizState.IO_PASS_APC_HEATING_MODE
                ),
            )
        ]

        return mode if mode is not None else PRESET_NONE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""

        if self.is_using_derogated_temperature_fallback:
            return await super().async_set_preset_mode(preset_mode)

        mode = PRESET_MODES_TO_OVERKIZ[preset_mode]

        # For consistency, it is better both are synced like on the Thermostat.
        await self.executor.async_execute_command(
            OverkizCommand.SET_PASS_APC_HEATING_MODE, mode
        )
        await self.executor.async_execute_command(
            OverkizCommand.SET_PASS_APC_COOLING_MODE, mode
        )

        await self.async_refresh_modes()

    @property
    def target_temperature(self) -> float:
        """Return hvac target temperature."""

        if self.is_using_derogated_temperature_fallback:
            return super().target_temperature

        if self.zone_control_hvac_mode == HVACMode.COOL:
            return cast(
                float,
                self.executor.select_state(
                    OverkizState.CORE_COOLING_TARGET_TEMPERATURE
                ),
            )

        if self.zone_control_hvac_mode == HVACMode.HEAT:
            return cast(
                float,
                self.executor.select_state(
                    OverkizState.CORE_HEATING_TARGET_TEMPERATURE
                ),
            )

        return cast(
            float, self.executor.select_state(OverkizState.CORE_TARGET_TEMPERATURE)
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""

        if self.is_using_derogated_temperature_fallback:
            return await super().async_set_temperature(**kwargs)

        temperature = kwargs[ATTR_TEMPERATURE]

        # Change both (heating/cooling) temperature is a good way to have consistency
        await self.executor.async_execute_command(
            OverkizCommand.SET_HEATING_TARGET_TEMPERATURE,
            temperature,
        )
        await self.executor.async_execute_command(
            OverkizCommand.SET_COOLING_TARGET_TEMPERATURE,
            temperature,
        )
        await self.executor.async_execute_command(
            OverkizCommand.SET_DEROGATION_ON_OFF_STATE,
            OverkizCommandParam.OFF,
        )

        # Target temperature may take up to 1 minute to get refreshed.
        await self.executor.async_execute_command(
            OverkizCommand.REFRESH_TARGET_TEMPERATURE
        )

    async def async_refresh_modes(self) -> None:
        """Refresh the device modes to have new states."""

        # The device needs a bit of time to update everything before a refresh.
        await sleep(2)

        await self.executor.async_execute_command(
            OverkizCommand.REFRESH_PASS_APC_HEATING_MODE
        )

        await self.executor.async_execute_command(
            OverkizCommand.REFRESH_PASS_APC_HEATING_PROFILE
        )

        await self.executor.async_execute_command(
            OverkizCommand.REFRESH_PASS_APC_COOLING_MODE
        )

        await self.executor.async_execute_command(
            OverkizCommand.REFRESH_PASS_APC_COOLING_PROFILE
        )

        await self.executor.async_execute_command(
            OverkizCommand.REFRESH_TARGET_TEMPERATURE
        )
