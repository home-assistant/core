"""Valve platform for the Ouman EH-800 integration."""

from dataclasses import dataclass

from ouman_eh_800_api import IntControlOumanEndpoint, L1BaseEndpoints, L2BaseEndpoints

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityDescription,
    ValveEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import OumanDevice
from .coordinator import OumanEh800ConfigEntry
from .entity import OumanEh800Entity, OumanEh800EntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class OumanEh800ValveEntityDescription(
    OumanEh800EntityDescription, ValveEntityDescription
):
    """Valve description with main/L1/L2 device assignment."""


VALVE_DESCRIPTIONS: dict[IntControlOumanEndpoint, OumanEh800ValveEntityDescription] = {
    L1BaseEndpoints.VALVE_POSITION_SETPOINT: OumanEh800ValveEntityDescription(
        device=OumanDevice.L1,
        key="valve_position_setpoint",
        translation_key="valve_position_setpoint",
        device_class=ValveDeviceClass.WATER,
    ),
    L2BaseEndpoints.VALVE_POSITION_SETPOINT: OumanEh800ValveEntityDescription(
        device=OumanDevice.L2,
        key="valve_position_setpoint",
        translation_key="valve_position_setpoint",
        device_class=ValveDeviceClass.WATER,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OumanEh800ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ouman EH-800 valve entities based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        OumanEh800ValveEntity(coordinator, endpoint, description)
        for endpoint in coordinator.data
        if isinstance(endpoint, IntControlOumanEndpoint)
        and (description := VALVE_DESCRIPTIONS.get(endpoint)) is not None
    )


class OumanEh800ValveEntity(OumanEh800Entity, ValveEntity):
    """Ouman EH-800 valve entity."""

    entity_description: OumanEh800ValveEntityDescription
    _endpoint: IntControlOumanEndpoint

    _attr_reports_position = True
    _attr_supported_features = (
        ValveEntityFeature.SET_POSITION
        | ValveEntityFeature.OPEN
        | ValveEntityFeature.CLOSE
    )

    @property
    def current_valve_position(self) -> int:
        """Return the current valve position 0-100."""
        value = self.coordinator.data[self._endpoint]
        assert isinstance(value, float)
        return int(value)

    async def async_set_valve_position(self, position: int) -> None:
        """Move the valve to the given position."""
        await self.coordinator.async_set_endpoint_value(self._endpoint, position)
