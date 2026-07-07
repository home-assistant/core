"""Support for Synology DSM select entities."""

from dataclasses import dataclass
from typing import override

from synology_dsm.api.core.hardware import FanSpeed, SynoCoreHardware

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SynoApi
from .coordinator import SynologyDSMCentralUpdateCoordinator, SynologyDSMConfigEntry
from .entity import SynologyDSMBaseEntity, SynologyDSMEntityDescription

FAN_SPEED_MAP = {
    FanSpeed.QUIET_STOP: "low_power",
    FanSpeed.QUIET: "quiet",
    FanSpeed.COOL: "cool",
    FanSpeed.FULL: "full_speed",
}
FAN_SPEED_MAP_INVERSE = {v: k for k, v in FAN_SPEED_MAP.items()}


@dataclass(frozen=True, kw_only=True)
class SynologyDSMSelectEntityDescription(
    SynologyDSMEntityDescription, SelectEntityDescription
):
    """Describes Synology DSM select entity."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SynologyDSMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set select entities for device."""
    data = entry.runtime_data
    if data.api.hardware is not None:
        async_add_entities(
            [SynologyDSMFanSpeedMode(data.api, data.coordinator_central)]
        )


class SynologyDSMFanSpeedMode(
    SynologyDSMBaseEntity[SynologyDSMCentralUpdateCoordinator], SelectEntity
):
    """Represent a Synology DSM fan speed mode select entity."""

    entity_description: SynologyDSMSelectEntityDescription

    def __init__(
        self,
        api: SynoApi,
        coordinator: SynologyDSMCentralUpdateCoordinator,
    ) -> None:
        """Initialize a Synology DSM select entity."""
        description = SynologyDSMSelectEntityDescription(
            api_key=SynoCoreHardware.API_KEY,
            key="fan_speed_mode",
            translation_key="fan_speed_mode",
            entity_category=EntityCategory.CONFIG,
        )
        self._attr_options = [
            val
            for fs, val in FAN_SPEED_MAP.items()
            if fs in api.dsm.hardware.supported_fan_speeds
        ]
        super().__init__(api, coordinator, description)

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return FAN_SPEED_MAP[self._api.dsm.hardware.fan_speed]

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the fan speed mode."""
        await self._api.dsm.hardware.set_fan_speed(FAN_SPEED_MAP_INVERSE[option])
        await self._api.dsm.hardware.update()
        self.async_write_ha_state()
