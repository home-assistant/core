"""Select platform for Zonneplan."""

from typing import override

from pyzonneplan import BatteryControlMode
from pyzonneplan.const import BatteryMode

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ZonneplanBatteryControlCoordinator, ZonneplanConfigEntry
from .entity import ZonneplanContractEntity

PARALLEL_UPDATES = 1

CONTROL_MODE_DESCRIPTION = SelectEntityDescription(
    key="control_mode",
    translation_key="control_mode",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZonneplanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Zonneplan select platform."""
    battery_coordinator = entry.runtime_data.battery_coordinator
    control_coordinator = entry.runtime_data.battery_control_coordinator

    async_add_entities(
        ZonneplanBatteryControlModeSelect(
            control_coordinator,
            contract_uuid,
            battery_data.battery.contract,
            CONTROL_MODE_DESCRIPTION,
        )
        for contract_uuid, battery_data in battery_coordinator.data.items()
    )


class ZonneplanBatteryControlModeSelect(
    ZonneplanContractEntity[ZonneplanBatteryControlCoordinator], SelectEntity
):
    """Representation of the control mode of a Zonneplan home battery."""

    @property
    def _control_mode(self) -> BatteryControlMode | None:
        """Return the control mode, None until it was fetched once."""
        return (self.coordinator.data or {}).get(self._contract_uuid)

    @property
    @override
    def available(self) -> bool:
        """Return if the control mode is known."""
        return super().available and self._control_mode is not None

    @property
    @override
    def options(self) -> list[str]:
        """Return the modes the battery supports, and the current one."""
        if (control_mode := self._control_mode) is None:
            return []
        available_modes = control_mode.available_modes
        return [
            mode.value
            for mode in BatteryMode
            if mode in available_modes or mode == control_mode.control_mode
        ]

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current control mode."""
        return self.coordinator.data[self._contract_uuid].control_mode

    @override
    async def async_select_option(self, option: str) -> None:
        """Switch the battery to another control mode."""
        await self.coordinator.async_set_control_mode(
            self._contract_uuid, BatteryMode(option)
        )
