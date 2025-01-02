"""Support for Atlantic Pass APC Zone Control."""

from typing import cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature

from ..coordinator import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity

OVERKIZ_TO_HVAC_MODE: dict[str, HVACMode] = {
    OverkizCommandParam.HEATING: HVACMode.HEAT,
    OverkizCommandParam.DRYING: HVACMode.DRY,
    OverkizCommandParam.COOLING: HVACMode.COOL,
    OverkizCommandParam.STOP: HVACMode.OFF,
}

HVAC_MODE_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_HVAC_MODE.items()}


class AtlanticPassAPCZoneControl(OverkizEntity, ClimateEntity):
    """Representation of Atlantic Pass APC Zone Control."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
    )

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)

        self._attr_hvac_modes = [*HVAC_MODE_TO_OVERKIZ]

        # Cooling is supported by a separate command
        if self.is_auto_hvac_mode_available:
            self._attr_hvac_modes.append(HVACMode.AUTO)

    @property
    def is_auto_hvac_mode_available(self) -> bool:
        """Check if auto mode is available on the ZoneControl."""

        return self.executor.has_command(
            OverkizCommand.SET_HEATING_COOLING_AUTO_SWITCH
        ) and self.executor.has_state(OverkizState.CORE_HEATING_COOLING_AUTO_SWITCH)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""

        if (
            self.is_auto_hvac_mode_available
            and cast(
                str,
                self.executor.select_state(
                    OverkizState.CORE_HEATING_COOLING_AUTO_SWITCH
                ),
            )
            == OverkizCommandParam.ON
        ):
            return HVACMode.AUTO

        return OVERKIZ_TO_HVAC_MODE[
            cast(
                str, self.executor.select_state(OverkizState.IO_PASS_APC_OPERATING_MODE)
            )
        ]

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""

        if self.is_auto_hvac_mode_available:
            await self.executor.async_execute_command(
                OverkizCommand.SET_HEATING_COOLING_AUTO_SWITCH,
                OverkizCommandParam.ON
                if hvac_mode == HVACMode.AUTO
                else OverkizCommandParam.OFF,
            )

        if hvac_mode == HVACMode.AUTO:
            return

        await self.executor.async_execute_command(
            OverkizCommand.SET_PASS_APC_OPERATING_MODE, HVAC_MODE_TO_OVERKIZ[hvac_mode]
        )
