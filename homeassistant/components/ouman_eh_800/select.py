"""Select platform for the Ouman EH-800 integration."""

from dataclasses import dataclass

from ouman_eh_800_api import (
    ControlEnum,
    EnumControlOumanEndpoint,
    L1BaseEndpoints,
    L2BaseEndpoints,
    RelayL1ValvePosition,
    RelayPumpSummerStop,
    RelayTempDifference,
    RelayTemperature,
    RelayTimeProgram,
    SystemEndpoints,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import OumanDevice
from .coordinator import OumanEh800ConfigEntry, OumanEh800Coordinator
from .entity import OumanEh800Entity, OumanEh800EntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class OumanEh800SelectEntityDescription(
    OumanEh800EntityDescription, SelectEntityDescription
):
    """Select description with main/L1/L2 device assignment."""


def _select_entity(
    *,
    device: OumanDevice,
    key: str,
) -> OumanEh800SelectEntityDescription:
    return OumanEh800SelectEntityDescription(
        device=device,
        key=key,
        translation_key=key,
    )


SELECT_DESCRIPTIONS: dict[
    EnumControlOumanEndpoint, OumanEh800SelectEntityDescription
] = {
    SystemEndpoints.HOME_AWAY_MODE: _select_entity(
        device=OumanDevice.MAIN, key="home_away_mode"
    ),
    L1BaseEndpoints.OPERATION_MODE: _select_entity(
        device=OumanDevice.L1, key="operation_mode"
    ),
    L2BaseEndpoints.OPERATION_MODE: _select_entity(
        device=OumanDevice.L2, key="operation_mode"
    ),
    RelayPumpSummerStop.CONTROL: _select_entity(
        device=OumanDevice.MAIN, key="relay_pump_summer_stop_control"
    ),
    RelayTemperature.CONTROL: _select_entity(
        device=OumanDevice.MAIN, key="relay_control"
    ),
    RelayTempDifference.CONTROL: _select_entity(
        device=OumanDevice.MAIN, key="relay_control"
    ),
    RelayL1ValvePosition.CONTROL: _select_entity(
        device=OumanDevice.MAIN, key="relay_control"
    ),
    RelayTimeProgram.CONTROL: _select_entity(
        device=OumanDevice.MAIN, key="relay_control"
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OumanEh800ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ouman EH-800 select entities based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        OumanEh800SelectEntity(coordinator, endpoint, description)
        for endpoint in coordinator.data
        if isinstance(endpoint, EnumControlOumanEndpoint)
        and (description := SELECT_DESCRIPTIONS.get(endpoint)) is not None
    )


class OumanEh800SelectEntity(OumanEh800Entity, SelectEntity):
    """Ouman EH-800 select entity."""

    entity_description: OumanEh800SelectEntityDescription
    _endpoint: EnumControlOumanEndpoint

    def __init__(
        self,
        coordinator: OumanEh800Coordinator,
        endpoint: EnumControlOumanEndpoint,
        description: OumanEh800SelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, endpoint, description)
        self._attr_options = [member.name.lower() for member in endpoint.enum_type]

    @property
    def current_option(self) -> str:
        """Return the currently selected option."""
        value = self.coordinator.data[self._endpoint]
        assert isinstance(value, ControlEnum)
        return value.name.lower()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option on the device."""
        await self.coordinator.async_set_endpoint_value(
            self._endpoint, self._endpoint.enum_type[option.upper()]
        )
