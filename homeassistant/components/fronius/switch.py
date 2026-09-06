"""Switch entities for the Fronius Modbus controls."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import FroniusEntity, FroniusEntityDescription, ModbusComponentFn

if TYPE_CHECKING:
    from . import FroniusConfigEntry
    from .coordinator import FroniusModbusSettingsUpdateCoordinator

# writes go to one device at a time
PARALLEL_UPDATES: Final = 1


@dataclass(frozen=True, kw_only=True)
class FroniusSwitchEntityDescription(FroniusEntityDescription, SwitchEntityDescription):
    """Describes a Fronius Modbus switch entity.

    ``field`` is the writable field of the model the control lives in.
    """

    component_fn: ModbusComponentFn
    field: str


MODBUS_SWITCH_ENTITY_DESCRIPTIONS: list[FroniusSwitchEntityDescription] = [
    FroniusSwitchEntityDescription(
        key="ac_power_limit_enabled",
        component_fn=lambda inverter: inverter.controls,
        field="enabled",
        entity_category=EntityCategory.CONFIG,
    ),
    FroniusSwitchEntityDescription(
        key="battery_charge_power_limit_enabled",
        component_fn=lambda inverter: inverter.storage,
        field="charge_limit_enabled",
        entity_category=EntityCategory.CONFIG,
    ),
    FroniusSwitchEntityDescription(
        key="battery_discharge_power_limit_enabled",
        component_fn=lambda inverter: inverter.storage,
        field="discharge_limit_enabled",
        entity_category=EntityCategory.CONFIG,
    ),
    FroniusSwitchEntityDescription(
        key="battery_grid_charging",
        component_fn=lambda inverter: inverter.storage,
        field="grid_charging",
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FroniusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fronius switch entities based on a config entry."""
    for coordinator in config_entry.runtime_data.modbus_settings_coordinators:
        coordinator.add_entities_for_seen_keys(
            async_add_entities, Platform.SWITCH, ModbusControlSwitch
        )


class ModbusControlSwitch(FroniusEntity, SwitchEntity):
    """A control of an inverters Modbus interface that is on or off.

    Turning a limit off doesn't lift it - it hands control back to the next
    priority source, which may impose a limit of its own. To override such a
    source, leave the limit on and set its setpoint to 100%.
    """

    entity_description: FroniusSwitchEntityDescription
    coordinator: FroniusModbusSettingsUpdateCoordinator

    def __init__(
        self,
        coordinator: FroniusModbusSettingsUpdateCoordinator,
        description: FroniusSwitchEntityDescription,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius Modbus control switch."""
        super().__init__(coordinator, description, solar_net_id)
        self._attr_device_info = coordinator.inverter_info.device_info
        self._attr_unique_id = (
            f"{coordinator.inverter_info.unique_id}-modbus-{description.key}"
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the control is active as the device reports it."""
        return self._device_data()[self.response_key]["value"]  # type: ignore[no-any-return]

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate the control."""
        await self._async_write(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Deactivate the control."""
        await self._async_write(False)

    async def _async_write(self, value: bool) -> None:
        await self.coordinator.async_write(
            self.entity_description.component_fn, self.entity_description.field, value
        )
