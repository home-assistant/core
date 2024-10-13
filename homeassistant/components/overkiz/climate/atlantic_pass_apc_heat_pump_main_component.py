"""Support for Atlantic Pass APC Heat Pump Main Component."""

from __future__ import annotations

from asyncio import sleep
from typing import cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature

from ..const import DOMAIN
from ..entity import OverkizEntity

OVERKIZ_TO_HVAC_MODES: dict[str, HVACMode] = {
    OverkizCommandParam.STOP: HVACMode.OFF,
    OverkizCommandParam.HEATING: HVACMode.HEAT,
    OverkizCommandParam.COOLING: HVACMode.COOL,
}

HVAC_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_HVAC_MODES.items()}


class AtlanticPassAPCHeatPumpMainComponent(OverkizEntity, ClimateEntity):
    """Representation of Atlantic Pass APC Heat Pump Main Component.

    This component can only turn off the heating pump and select the working mode: heating or cooling.
    To set new temperatures, they must be selected individually per Zones (ie: AtlanticPassAPCHeatingAndCoolingZone).
    Once the Device is switched on into heating or cooling mode, the Heat Pump will be activated and will use
    the default temperature configuration for each available zone.
    """

    _attr_hvac_modes = [*HVAC_MODES_TO_OVERKIZ]
    _attr_supported_features = (
        ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = DOMAIN
    _enable_turn_on_off_backwards_compatibility = False

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac current mode: stop, cooling, heating."""
        return OVERKIZ_TO_HVAC_MODES[
            cast(
                str, self.executor.select_state(OverkizState.IO_PASS_APC_OPERATING_MODE)
            )
        ]

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode: stop, cooling, heating."""
        # They are mainly managed by the Zone Control device
        # However, we can turn off or put the heat pump in cooling/ heating mode.
        await self.executor.async_execute_command(
            OverkizCommand.SET_PASS_APC_OPERATING_MODE,
            HVAC_MODES_TO_OVERKIZ[hvac_mode],
        )

        # Wait for 2 seconds to ensure the HVAC mode change is properly applied and system stabilizes.
        await sleep(2)
