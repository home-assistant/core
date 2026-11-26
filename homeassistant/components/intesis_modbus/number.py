"""Numbers for the settings of the air conditioner behind an Intesis gateway."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final, override

from intesis_gw_modbus import IntesisSingleUnitGateway

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import IntesisConfigEntry, IntesisUnitCoordinator
from .entity import IntesisEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class IntesisNumberEntityDescription(NumberEntityDescription):
    """A setting, and where to read and write it on the gateway."""

    report_name: str
    value_fn: Callable[[IntesisSingleUnitGateway], float | None]
    set_fn: Callable[[IntesisSingleUnitGateway, float], Awaitable[None]]
    step_fn: Callable[[IntesisSingleUnitGateway], float] | None = None


NUMBERS: Final[tuple[IntesisNumberEntityDescription, ...]] = (
    IntesisNumberEntityDescription(
        key="external_temperature",
        translation_key="external_temperature",
        report_name="limits",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_max_value=38,
        native_min_value=10,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda device: device.external_temperature,
        set_fn=lambda device, value: device.async_set_external_temperature(value),
        step_fn=lambda device: device.setpoint_step,
    ),
    IntesisNumberEntityDescription(
        key="window_timeout",
        translation_key="window_timeout",
        report_name="control",
        device_class=NumberDeviceClass.DURATION,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        mode=NumberMode.BOX,
        native_max_value=30,
        native_min_value=0,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda device: device.window_timeout_minutes,
        set_fn=lambda device, value: device.async_set_window_timeout(int(value)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntesisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the numbers of the air conditioner behind the gateway."""
    async_add_entities(
        IntesisNumber(entry.runtime_data.unit, description) for description in NUMBERS
    )


class IntesisNumber(IntesisEntity, NumberEntity):
    """A setting of the air conditioner behind an Intesis gateway."""

    entity_description: IntesisNumberEntityDescription

    def __init__(
        self,
        coordinator: IntesisUnitCoordinator,
        description: IntesisNumberEntityDescription,
    ) -> None:
        """Bind to the device the description reads, through its coordinator."""
        super().__init__(coordinator, description.key, description.report_name)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> float | None:
        """The value the gateway reported in the most recent poll."""
        return self.entity_description.value_fn(self.coordinator.device)

    @property
    @override
    def native_step(self) -> float | None:
        """The step the gateway's temperature format allows, or the fixed one."""
        if (step_fn := self.entity_description.step_fn) is not None:
            return step_fn(self.coordinator.device)
        return super().native_step

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Write the value to the gateway."""
        await self._async_write(
            lambda: self.entity_description.set_fn(self.coordinator.device, value)
        )
