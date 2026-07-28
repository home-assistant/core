"""GoodWe PV inverter numeric settings entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import override

from goodwe import Inverter, InverterError, OperationMode

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    RestoreNumber,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import GoodweConfigEntry, GoodweRuntimeData

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class GoodweNumberEntityDescription(NumberEntityDescription):
    """Class describing Goodwe number entities."""

    getter: Callable[[Inverter], Awaitable[int]]
    setter: Callable[[Inverter, int], Awaitable[None]]
    filter: Callable[[Inverter], bool]


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
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GoodweConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the inverter select entities from a config entry."""
    inverter = config_entry.runtime_data.inverter
    device_info = config_entry.runtime_data.device_info

    entities: list[NumberEntity] = []

    for description in filter(lambda dsc: dsc.filter(inverter), NUMBERS):
        try:
            current_value = await description.getter(inverter)
        except InverterError, ValueError:
            # Inverter model does not support this setting
            _LOGGER.debug("Could not read inverter setting %s", description.key)
            continue

        entities.append(
            InverterNumberEntity(device_info, description, inverter, current_value)
        )

    runtime_data = config_entry.runtime_data
    supported_modes = await inverter.get_operation_modes(True)
    if OperationMode.ECO_CHARGE in supported_modes or (
        OperationMode.ECO_DISCHARGE in supported_modes
    ):
        entities.extend(
            EcoModeNumberEntity(device_info, eco_description, inverter, runtime_data)
            for eco_description in ECO_MODE_NUMBERS
        )

    async_add_entities(entities)


class InverterNumberEntity(NumberEntity):
    """Inverter numeric setting entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    entity_description: GoodweNumberEntityDescription

    def __init__(
        self,
        device_info: DeviceInfo,
        description: GoodweNumberEntityDescription,
        inverter: Inverter,
        current_value: int,
    ) -> None:
        """Initialize the number inverter setting entity."""
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}-{description.key}-{inverter.serial_number}"  # pylint: disable=home-assistant-entity-unique-id-redundant-domain
        self._attr_device_info = device_info
        self._attr_native_value = float(current_value)
        self._inverter: Inverter = inverter

    async def async_update(self) -> None:
        """Get the current value from inverter."""
        value = await self.entity_description.getter(self._inverter)
        self._attr_native_value = float(value)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.entity_description.setter(self._inverter, int(value))
        self._attr_native_value = value
        self.async_write_ha_state()


@dataclass(frozen=True, kw_only=True)
class EcoModeNumberEntityDescription(NumberEntityDescription):
    """Number entity backed by GoodweRuntimeData instead of an inverter register."""

    attr_name: str


ECO_MODE_NUMBERS = (
    EcoModeNumberEntityDescription(
        key="eco_mode_power",
        translation_key="eco_mode_power",
        icon="mdi:battery-charging-high",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        attr_name="eco_mode_power",
    ),
    EcoModeNumberEntityDescription(
        key="eco_mode_soc",
        translation_key="eco_mode_soc",
        icon="mdi:battery-charging-100",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        attr_name="eco_mode_soc",
    ),
)


class EcoModeNumberEntity(RestoreNumber):
    """Power/SoC parameters used the next time ECO_CHARGE/ECO_DISCHARGE is selected.

    Not an inverter register - the value only lives in GoodweRuntimeData and
    is read by InverterOperationModeEntity when the select entity is set to
    eco_charge/eco_discharge. GoodweRuntimeData itself is recreated with the
    100/100 defaults on every reload, so this entity restores its last known
    value (via RestoreNumber) and writes it back into GoodweRuntimeData on
    startup, keeping the two in sync.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    entity_description: EcoModeNumberEntityDescription

    def __init__(
        self,
        device_info: DeviceInfo,
        description: EcoModeNumberEntityDescription,
        inverter: Inverter,
        runtime_data: GoodweRuntimeData,
    ) -> None:
        """Initialize the eco mode parameter entity."""
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}-{description.key}-{inverter.serial_number}"  # pylint: disable=home-assistant-entity-unique-id-redundant-domain
        self._attr_device_info = device_info
        self._runtime_data = runtime_data
        self._attr_native_value = float(getattr(runtime_data, description.attr_name))

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last known value, if any, on startup."""
        await super().async_added_to_hass()
        last_data = await self.async_get_last_number_data()
        if last_data is not None and last_data.native_value is not None:
            self._attr_native_value = last_data.native_value
            setattr(
                self._runtime_data,
                self.entity_description.attr_name,
                int(last_data.native_value),
            )

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        setattr(self._runtime_data, self.entity_description.attr_name, int(value))
        self._attr_native_value = value
        self.async_write_ha_state()
