"""Binary sensor platform for the Ouman EH-800 integration."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from ouman_eh_800_api import (
    L1BaseEndpoints,
    OumanEndpoint,
    RelayL1ValvePosition,
    RelayPumpSummerStop,
    RelayTempDifference,
    RelayTemperature,
    RelayTimeProgram,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import OumanDevice
from .coordinator import OumanEh800ConfigEntry
from .entity import (
    OumanEh800EndpointEntity,
    OumanEh800Entity,
    OumanEh800EntityDescription,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OumanEh800BinarySensorEntityDescription(
    OumanEh800EntityDescription, BinarySensorEntityDescription
):
    """Binary sensor description with main/L1/L2 device assignment."""


SUMMER_FUNCTION_DESCRIPTION = OumanEh800BinarySensorEntityDescription(
    device=OumanDevice.L1,
    key="summer_function",
    translation_key="summer_function",
)

RELAY_DESCRIPTION = OumanEh800BinarySensorEntityDescription(
    device=OumanDevice.MAIN,
    key="relay",
    translation_key="relay",
)

BINARY_SENSOR_DESCRIPTIONS: dict[
    OumanEndpoint, OumanEh800BinarySensorEntityDescription
] = {
    RelayPumpSummerStop.PUMP_RUNNING: OumanEh800BinarySensorEntityDescription(
        device=OumanDevice.MAIN,
        key="circulation_pump",
        translation_key="circulation_pump",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    RelayTemperature.RELAY_ON: RELAY_DESCRIPTION,
    RelayTempDifference.RELAY_ON: RELAY_DESCRIPTION,
    RelayL1ValvePosition.RELAY_ON: RELAY_DESCRIPTION,
    RelayTimeProgram.RELAY_ON: RELAY_DESCRIPTION,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OumanEh800ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ouman EH-800 binary sensors based on a config entry."""
    coordinator = entry.runtime_data
    entities: list[OumanEh800Entity] = []
    if L1BaseEndpoints.CIRCUIT_NAME in coordinator.data.values:
        entities.append(
            OumanEh800SummerFunctionBinarySensor(
                coordinator, SUMMER_FUNCTION_DESCRIPTION
            )
        )
    entities.extend(
        OumanEh800BinarySensorEntity(coordinator, endpoint, description)
        for endpoint in coordinator.data.values
        if (description := BINARY_SENSOR_DESCRIPTIONS.get(endpoint)) is not None
    )
    async_add_entities(entities)


class OumanEh800SummerFunctionBinarySensor(OumanEh800Entity, BinarySensorEntity):
    """Reports whether the summer function is holding the L1 valve closed."""

    entity_description: OumanEh800BinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool:
        """Return True when the summer function is active."""
        return self.coordinator.data.l1_summer_function_active


class OumanEh800BinarySensorEntity(OumanEh800EndpointEntity, BinarySensorEntity):
    """Ouman EH-800 binary sensor backed by a boolean endpoint."""

    entity_description: OumanEh800BinarySensorEntityDescription

    @property
    @override
    def available(self) -> bool:
        """Return False when the device text could not be parsed to a state."""
        return (
            super().available
            and self.coordinator.data.values[self._endpoint] is not None
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return the endpoint state."""
        value = self.coordinator.data.values[self._endpoint]
        if TYPE_CHECKING:
            assert isinstance(value, bool)
        return value
