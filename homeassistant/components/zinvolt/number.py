"""Number platform for Zinvolt integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from zinvolt import ZinvoltClient
from zinvolt.models import BatteryState

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ZinvoltConfigEntry, ZinvoltDeviceCoordinator
from .entity import ZinvoltEntity


@dataclass(kw_only=True, frozen=True)
class ZinvoltBatteryStateDescription(NumberEntityDescription):
    """Number description for Zinvolt battery state."""

    max_fn: Callable[[BatteryState], int] | None = None
    value_fn: Callable[[BatteryState], int]
    set_value_fn: Callable[[ZinvoltClient, str, int], Awaitable[None]]


NUMBERS: tuple[ZinvoltBatteryStateDescription, ...] = (
    ZinvoltBatteryStateDescription(
        key="max_output",
        translation_key="max_output",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda state: state.global_settings.max_output,
        set_value_fn=lambda client, battery_id, value: client.set_max_output(
            battery_id, value
        ),
        native_min_value=0,
        max_fn=lambda state: state.global_settings.max_output_limit,
    ),
    ZinvoltBatteryStateDescription(
        key="upper_threshold",
        translation_key="upper_threshold",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda state: state.global_settings.battery_upper_threshold,
        set_value_fn=lambda client, battery_id, value: client.set_upper_threshold(
            battery_id, value
        ),
        native_min_value=0,
        native_max_value=100,
    ),
    ZinvoltBatteryStateDescription(
        key="lower_threshold",
        translation_key="lower_threshold",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda state: state.global_settings.battery_lower_threshold,
        set_value_fn=lambda client, battery_id, value: client.set_lower_threshold(
            battery_id, value
        ),
        native_min_value=9,
        native_max_value=100,
    ),
    ZinvoltBatteryStateDescription(
        key="standby_time",
        translation_key="standby_time",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=NumberDeviceClass.DURATION,
        value_fn=lambda state: state.global_settings.standby_time,
        set_value_fn=lambda client, battery_id, value: client.set_standby_time(
            battery_id, value
        ),
        native_min_value=5,
        native_max_value=60,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZinvoltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize the entries."""

    async_add_entities(
        ZinvoltBatteryStateNumber(coordinator, description)
        for description in NUMBERS
        for coordinator in entry.runtime_data.values()
    )


class ZinvoltBatteryStateNumber(ZinvoltEntity, NumberEntity):
    """Zinvolt number."""

    entity_description: ZinvoltBatteryStateDescription

    def __init__(
        self,
        coordinator: ZinvoltDeviceCoordinator,
        description: ZinvoltBatteryStateDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.serial_number}.{description.key}"

    @property
    def native_max_value(self) -> float:
        """Return the native maximum value."""
        if self.entity_description.max_fn is None:
            return super().native_max_value
        return self.entity_description.max_fn(self.coordinator.data)

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_set_native_value(self, value: float) -> None:
        """Set the state of the sensor."""
        await self.entity_description.set_value_fn(
            self.coordinator.client, self.coordinator.battery.identifier, int(value)
        )
        await self.coordinator.async_request_refresh()
