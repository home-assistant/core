"""Number entities for the Fronius Modbus setpoints."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, override

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE, EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import FroniusEntity, FroniusEntityDescription, ModbusComponentFn

if TYPE_CHECKING:
    from . import FroniusConfigEntry
    from .coordinator import FroniusModbusSettingsUpdateCoordinator

# writes go to one device at a time
PARALLEL_UPDATES: Final = 1


@dataclass(frozen=True, kw_only=True)
class FroniusNumberEntityDescription(FroniusEntityDescription, NumberEntityDescription):
    """Describes a Fronius Modbus number entity.

    ``field`` is the writable field of the model the setpoint lives in, and
    ``enable_field`` the one that puts it into effect, where there is one.
    """

    component_fn: ModbusComponentFn
    field: str
    enable_field: str | None = None


MODBUS_NUMBER_ENTITY_DESCRIPTIONS: list[FroniusNumberEntityDescription] = [
    FroniusNumberEntityDescription(
        key="ac_power_limit",
        component_fn=lambda inverter: inverter.controls,
        field="power_limit",
        enable_field="enabled",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
    ),
    FroniusNumberEntityDescription(
        key="battery_charge_power_limit",
        component_fn=lambda inverter: inverter.storage,
        field="charge_limit",
        enable_field="charge_limit_enabled",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
    ),
    FroniusNumberEntityDescription(
        key="battery_discharge_power_limit",
        component_fn=lambda inverter: inverter.storage,
        field="discharge_limit",
        enable_field="discharge_limit_enabled",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
    ),
    FroniusNumberEntityDescription(
        key="battery_minimum_reserve",
        component_fn=lambda inverter: inverter.storage,
        field="minimum_reserve",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FroniusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fronius number entities based on a config entry."""
    for coordinator in config_entry.runtime_data.modbus_settings_coordinators:
        coordinator.add_entities_for_seen_keys(
            async_add_entities, Platform.NUMBER, ModbusSetpointNumber
        )


class ModbusSetpointNumber(FroniusEntity, NumberEntity):
    """A writable setpoint of an inverters Modbus interface."""

    entity_description: FroniusNumberEntityDescription
    coordinator: FroniusModbusSettingsUpdateCoordinator

    def __init__(
        self,
        coordinator: FroniusModbusSettingsUpdateCoordinator,
        description: FroniusNumberEntityDescription,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius Modbus setpoint."""
        super().__init__(coordinator, description, solar_net_id)
        self._attr_device_info = coordinator.inverter_info.device_info
        self._attr_unique_id = (
            f"{coordinator.inverter_info.unique_id}-modbus-{description.key}"
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the setpoint as the device reports it."""
        return self._device_data()[self.response_key]["value"]  # type: ignore[no-any-return]

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Write the setpoint to the device."""
        await self.coordinator.async_write(
            self.entity_description.component_fn,
            self.entity_description.field,
            value,
            enable_field=self.entity_description.enable_field,
        )
