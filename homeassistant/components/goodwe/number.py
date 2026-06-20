"""GoodWe PV inverter numeric settings entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
import logging

from goodwe import Inverter, InverterError

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import GoodweConfigEntry, GoodweUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class GoodweNumberEntityDescription(NumberEntityDescription):
    """Class describing Goodwe number entities."""

    getter: Callable[[Inverter], Awaitable[int]]
    setter: Callable[[Inverter, int], Awaitable[None]]
    filter: Callable[[Inverter], bool]
    # Optional sensor id whose runtime value becomes native_max_value.
    # Falls back to native_max_value from the description when not set or unavailable.
    max_sensor_id: str | None = field(default=None)


def _get_setting_unit(inverter: Inverter, setting: str) -> str:
    """Return the unit of an inverter setting."""
    return next((s.unit for s in inverter.settings() if s.id_ == setting), "")


NUMBERS = (
    # Only one of the export limits are added.
    # Availability is checked in the filter method.
    # Export limit in W
    GoodweNumberEntityDescription(
        key="grid_export_limit",
        translation_key="grid_export_limit",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_step=100,
        native_min_value=0,
        native_max_value=10000,
        getter=lambda inv: inv.get_grid_export_limit(),
        setter=lambda inv, val: inv.set_grid_export_limit(val),
        filter=lambda inv: _get_setting_unit(inv, "grid_export_limit") != "%",
    ),
    # Export limit in %
    GoodweNumberEntityDescription(
        key="grid_export_limit",
        translation_key="grid_export_limit",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        native_step=1,
        native_min_value=0,
        native_max_value=200,
        getter=lambda inv: inv.get_grid_export_limit(),
        setter=lambda inv, val: inv.set_grid_export_limit(val),
        filter=lambda inv: _get_setting_unit(inv, "grid_export_limit") == "%",
    ),
    GoodweNumberEntityDescription(
        key="battery_discharge_depth",
        translation_key="battery_discharge_depth",
        icon="mdi:battery-arrow-down",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        native_step=1,
        native_min_value=0,
        native_max_value=99,
        getter=lambda inv: inv.get_ongrid_battery_dod(),
        setter=lambda inv, val: inv.set_ongrid_battery_dod(val),
        filter=lambda inv: True,
    ),
    GoodweNumberEntityDescription(
        key="battery_charge_current",
        translation_key="battery_charge_current",
        icon="mdi:battery-arrow-up",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        native_step=0.1,
        native_min_value=0,
        native_max_value=100,
        max_sensor_id="battery_charge_limit",
        getter=lambda inv: inv.read_setting("battery_charge_current"),
        setter=lambda inv, val: inv.write_setting("battery_charge_current", val),
        filter=lambda inv: "battery_charge_current" in {s.id_ for s in inv.settings()},
    ),
    GoodweNumberEntityDescription(
        key="battery_discharge_current",
        translation_key="battery_discharge_current",
        icon="mdi:battery-arrow-down",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        native_step=0.1,
        native_min_value=0,
        native_max_value=100,
        max_sensor_id="battery_discharge_limit",
        getter=lambda inv: inv.read_setting("battery_discharge_current"),
        setter=lambda inv, val: inv.write_setting("battery_discharge_current", val),
        filter=lambda inv: (
            "battery_discharge_current" in {s.id_ for s in inv.settings()}
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GoodweConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the inverter select entities from a config entry."""
    inverter = config_entry.runtime_data.inverter
    coordinator = config_entry.runtime_data.coordinator
    device_info = config_entry.runtime_data.device_info

    entities = []

    for description in filter(lambda dsc: dsc.filter(inverter), NUMBERS):
        try:
            current_value = await description.getter(inverter)
        except InverterError, ValueError:
            # Inverter model does not support this setting
            _LOGGER.debug("Could not read inverter setting %s", description.key)
            continue

        entities.append(
            InverterNumberEntity(
                coordinator, device_info, description, inverter, current_value
            )
        )

    async_add_entities(entities)


class InverterNumberEntity(NumberEntity):
    """Inverter numeric setting entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    entity_description: GoodweNumberEntityDescription

    def __init__(
        self,
        coordinator: GoodweUpdateCoordinator,
        device_info: DeviceInfo,
        description: GoodweNumberEntityDescription,
        inverter: Inverter,
        current_value: int,
    ) -> None:
        """Initialize the number inverter setting entity."""
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}-{description.key}-{inverter.serial_number}"
        self._attr_device_info = device_info
        self._attr_native_value = float(current_value)
        self._inverter: Inverter = inverter
        self._coordinator = coordinator

    @property
    def native_max_value(self) -> float:
        """Return max value, using the BMS-reported limit when available."""
        max_sensor_id = self.entity_description.max_sensor_id
        if max_sensor_id is not None:
            bms_limit = self._coordinator.sensor_value(max_sensor_id)
            if bms_limit is not None and bms_limit > 0:
                return float(bms_limit)
        return self.entity_description.native_max_value or 100.0

    async def async_update(self) -> None:
        """Get the current value from inverter."""
        value = await self.entity_description.getter(self._inverter)
        self._attr_native_value = float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.entity_description.setter(self._inverter, int(value))
        self._attr_native_value = value
        self.async_write_ha_state()
