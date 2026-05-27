"""Support for AtlanticDomesticHotWaterProductionV2_CE_FLAT IOComponent."""

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from .atlantic_domestic_hot_water_production_v2_io_component import (
    AtlanticDomesticHotWaterProductionV2IOComponent,
)


class AtlanticDomesticHotWaterProductionV2CEFlatIOComponent(
    AtlanticDomesticHotWaterProductionV2IOComponent
):
    """Representation of AtlanticDomesticHotWaterProductionV2_CE_FLAT (io).

    This variant uses setAbsenceMode instead of setCurrentOperatingMode
    and io:DHWAbsenceModeState instead of io:AwayModeDuration.
    """

    @property
    def is_away_mode_on(self) -> bool:
        """Return true if away mode is on."""
        return (
            self.executor.select_state(OverkizState.IO_DHW_ABSENCE_MODE)
            == OverkizCommandParam.ON
        )

    async def async_turn_away_mode_on(self, refresh_afterwards: bool = True) -> None:
        """Turn away mode on."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_ABSENCE_MODE,
            OverkizCommandParam.ON,
            refresh_afterwards=refresh_afterwards,
        )

    async def async_turn_away_mode_off(self, refresh_afterwards: bool = True) -> None:
        """Turn away mode off."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_ABSENCE_MODE,
            OverkizCommandParam.OFF,
            refresh_afterwards=refresh_afterwards,
        )
