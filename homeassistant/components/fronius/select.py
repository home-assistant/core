"""Select entities for the Fronius Modbus controls."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import discovery_signal
from .entity import FroniusEntity, FroniusEntityDescription, ModbusComponentFn

if TYPE_CHECKING:
    from . import FroniusConfigEntry
    from .coordinator import (
        FroniusCoordinatorBase,
        FroniusModbusSettingsUpdateCoordinator,
    )

# writes go to one device at a time
PARALLEL_UPDATES: Final = 1

BATTERY_FORCED_MODE_OFF: Final = "off"
BATTERY_FORCED_MODE_CHARGE: Final = "charge"
BATTERY_FORCED_MODE_DISCHARGE: Final = "discharge"


@dataclass(frozen=True, kw_only=True)
class FroniusSelectEntityDescription(FroniusEntityDescription, SelectEntityDescription):
    """Describes a Fronius Modbus select entity.

    ``option_writes`` maps each option to the fields of the model the control
    lives in, with the values to write to them in order.
    """

    component_fn: ModbusComponentFn
    option_writes: Mapping[str, Mapping[str, float | bool]]


# The battery limits are rates in percent of the maximum charge power, and a
# negative one turns the direction around: a discharge limit of -100% makes
# the battery charge at full power. The device refuses both rates negative at
# once, so the positive rate is written before the negative one. Turning
# forcing off releases both limits at 100%, so a limit switched on later
# doesn't pick up a negative rate.
MODBUS_SELECT_ENTITY_DESCRIPTIONS: list[FroniusSelectEntityDescription] = [
    FroniusSelectEntityDescription(
        key="battery_forced_mode",
        component_fn=lambda inverter: inverter.storage,
        options=[
            BATTERY_FORCED_MODE_OFF,
            BATTERY_FORCED_MODE_CHARGE,
            BATTERY_FORCED_MODE_DISCHARGE,
        ],
        option_writes={
            BATTERY_FORCED_MODE_OFF: {
                "charge_limit_enabled": False,
                "discharge_limit_enabled": False,
                "charge_limit": 100,
                "discharge_limit": 100,
                "grid_charging": False,
            },
            BATTERY_FORCED_MODE_CHARGE: {
                "grid_charging": True,
                "charge_limit": 100,
                "discharge_limit": -100,
                "charge_limit_enabled": True,
                "discharge_limit_enabled": True,
            },
            BATTERY_FORCED_MODE_DISCHARGE: {
                "discharge_limit": 100,
                "charge_limit": -100,
                "charge_limit_enabled": True,
                "discharge_limit_enabled": True,
            },
        },
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FroniusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fronius select entities based on a config entry."""
    solar_net = config_entry.runtime_data
    for coordinator in solar_net.modbus_settings_coordinators:
        coordinator.add_entities_for_seen_keys(
            async_add_entities, Platform.SELECT, ModbusControlSelect
        )

    @callback
    def async_add_new_entities(coordinator: FroniusCoordinatorBase) -> None:
        """Add the entities of a coordinator found after setup."""
        if Platform.SELECT not in coordinator.valid_descriptions:
            return
        coordinator.add_entities_for_seen_keys(
            async_add_entities, Platform.SELECT, ModbusControlSelect
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, discovery_signal(config_entry.entry_id), async_add_new_entities
        )
    )


class ModbusControlSelect(FroniusEntity, SelectEntity):
    """A control of an inverters Modbus interface with exclusive modes."""

    entity_description: FroniusSelectEntityDescription
    coordinator: FroniusModbusSettingsUpdateCoordinator

    def __init__(
        self,
        coordinator: FroniusModbusSettingsUpdateCoordinator,
        description: FroniusSelectEntityDescription,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius Modbus control select."""
        super().__init__(coordinator, description, solar_net_id)
        self._attr_device_info = coordinator.inverter_info.device_info
        self._attr_unique_id = (
            f"{coordinator.inverter_info.unique_id}-modbus-{description.key}"
        )

    @property
    @override
    def current_option(self) -> str | None:
        """Return the mode as the device reports it."""
        return self._device_data()[self.response_key]["value"]  # type: ignore[no-any-return]

    @override
    async def async_select_option(self, option: str) -> None:
        """Put the device into the selected mode."""
        await self.coordinator.async_write(
            self.entity_description.component_fn,
            self.entity_description.option_writes[option],
        )
