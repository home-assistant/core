"""Support for MELCloud device selects."""

from typing import override

from pymelcloud import DEVICE_TYPE_ATW
from pymelcloud.atw_device import (
    ZONE_OPERATION_MODE_COOL_FLOW,
    ZONE_OPERATION_MODE_COOL_THERMOSTAT,
    ZONE_OPERATION_MODE_CURVE,
    ZONE_OPERATION_MODE_HEAT_FLOW,
    ZONE_OPERATION_MODE_HEAT_THERMOSTAT,
    Zone,
)

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MelCloudConfigEntry, MelCloudDeviceUpdateCoordinator
from .entity import AtwZoneEntity

OPTION_ROOM = "room"
OPTION_FLOW = "flow"
OPTION_CURVE = "curve"

# The device bundles the heating/cooling direction and the control method into a
# single operation mode. The heat/cool direction is handled by the climate
# entity, so this select only exposes the method and keeps the current direction.
MODE_TO_OPTION = {
    ZONE_OPERATION_MODE_HEAT_THERMOSTAT: OPTION_ROOM,
    ZONE_OPERATION_MODE_COOL_THERMOSTAT: OPTION_ROOM,
    ZONE_OPERATION_MODE_HEAT_FLOW: OPTION_FLOW,
    ZONE_OPERATION_MODE_COOL_FLOW: OPTION_FLOW,
    ZONE_OPERATION_MODE_CURVE: OPTION_CURVE,
}
HEATING_OPTION_TO_MODE = {
    OPTION_ROOM: ZONE_OPERATION_MODE_HEAT_THERMOSTAT,
    OPTION_FLOW: ZONE_OPERATION_MODE_HEAT_FLOW,
    OPTION_CURVE: ZONE_OPERATION_MODE_CURVE,
}
COOLING_OPTION_TO_MODE = {
    OPTION_ROOM: ZONE_OPERATION_MODE_COOL_THERMOSTAT,
    OPTION_FLOW: ZONE_OPERATION_MODE_COOL_FLOW,
}
COOLING_MODES = {ZONE_OPERATION_MODE_COOL_THERMOSTAT, ZONE_OPERATION_MODE_COOL_FLOW}


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: MelCloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MELCloud selects based on config_entry."""
    coordinators = entry.runtime_data
    async_add_entities(
        AtwZoneOperationModeSelect(coordinator, zone)
        for coordinator in coordinators.get(DEVICE_TYPE_ATW, [])
        for zone in coordinator.device.zones
    )


class AtwZoneOperationModeSelect(AtwZoneEntity, SelectEntity):
    """Select for the temperature control method of an Air-to-Water zone."""

    _attr_translation_key = "operation_mode"

    def __init__(
        self,
        coordinator: MelCloudDeviceUpdateCoordinator,
        zone: Zone,
    ) -> None:
        """Initialize the operation mode select."""
        super().__init__(coordinator, zone)
        self._attr_unique_id = (
            f"{coordinator.device.serial}-{zone.zone_index}-operation_mode"
        )
        available = {
            MODE_TO_OPTION[mode]
            for mode in zone.operation_modes
            if mode in MODE_TO_OPTION
        }
        self._attr_options = [
            option
            for option in (OPTION_ROOM, OPTION_FLOW, OPTION_CURVE)
            if option in available
        ]

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current control method."""
        return MODE_TO_OPTION.get(self._zone.operation_mode)

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the control method, keeping the current heating/cooling direction."""
        if option != OPTION_CURVE and self._zone.operation_mode in COOLING_MODES:
            mode = COOLING_OPTION_TO_MODE[option]
        else:
            mode = HEATING_OPTION_TO_MODE[option]
        await self._zone.set_operation_mode(mode)
        await self.coordinator.async_request_refresh()
