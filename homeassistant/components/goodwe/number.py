"""GoodWe PV inverter numeric settings entities."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from goodwe import Inverter, InverterError

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENTITY_CATEGORY_CONFIG, PERCENTAGE, POWER_WATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    KEY_DEVICE_INFO,
    KEY_ECO_MODE_POWER,
    KEY_INVERTER,
    KEY_OPERATION_MODE,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class GoodweNumberEntityDescriptionBase:
    """Required values when describing Goodwe number entities."""

    getter: Callable[[Inverter], Awaitable[int]]
    setter: Callable[[Inverter, int], Awaitable[None]]


@dataclass
class GoodweNumberEntityDescription(
    NumberEntityDescription, GoodweNumberEntityDescriptionBase
):
    """Class describing Goodwe number entities."""


async def _set_eco_mode_power(entity: InverterNumberEntity, value: int) -> None:
    operation_mode_entity = entity.config[KEY_OPERATION_MODE]
    if operation_mode_entity:
        await operation_mode_entity.update_eco_mode_power(value)


NUMBERS = (
    GoodweNumberEntityDescription(
        key="grid_export_limit",
        name="Grid export limit",
        icon="mdi:transmission-tower",
        entity_category=ENTITY_CATEGORY_CONFIG,
        unit_of_measurement=POWER_WATT,
        getter=lambda inv: inv.get_grid_export_limit(),
        setter=lambda inv, val: inv.set_grid_export_limit(val),
        step=100,
        min_value=0,
        max_value=10000,
    ),
    GoodweNumberEntityDescription(
        key="battery_discharge_depth",
        name="Depth of discharge (on-grid)",
        icon="mdi:battery-arrow-down",
        entity_category=ENTITY_CATEGORY_CONFIG,
        unit_of_measurement=PERCENTAGE,
        getter=lambda inv: inv.get_ongrid_battery_dod(),
        setter=lambda inv, val: inv.set_ongrid_battery_dod(val),
        step=1,
        min_value=0,
        max_value=99,
    ),
    GoodweNumberEntityDescription(
        key="eco_mode_power",
        name="Eco mode power",
        icon="mdi:battery-charging-low",
        entity_category=ENTITY_CATEGORY_CONFIG,
        unit_of_measurement=PERCENTAGE,
        getter=lambda inv: inv.get_operation_mode(),
        setter=_set_eco_mode_power,
        step=1,
        min_value=0,
        max_value=100,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the inverter select entities from a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    inverter = domain_data[KEY_INVERTER]
    device_info = domain_data[KEY_DEVICE_INFO]

    entities = []

    for description in NUMBERS:
        try:
            current_value = await description.getter(inverter)
        except (InverterError, ValueError):
            # Inverter model does not support this setting
            _LOGGER.debug("Could not read inverter setting %s", description.key)
            continue

        entity = InverterNumberEntity(
            device_info, description, inverter, current_value, domain_data
        )
        if description.key == "eco_mode_power":
            domain_data[KEY_ECO_MODE_POWER] = entity

        entities.append(entity)

    async_add_entities(entities)


class InverterNumberEntity(NumberEntity):
    """Inverter numeric setting entity."""

    _attr_should_poll = False
    entity_description: GoodweNumberEntityDescription

    def __init__(
        self,
        device_info: DeviceInfo,
        description: GoodweNumberEntityDescription,
        inverter: Inverter,
        current_value: int,
        config: dict,
    ) -> None:
        """Initialize the number inverter setting entity."""
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}-{description.key}-{inverter.serial_number}"
        self._attr_device_info = device_info
        self._attr_value = float(current_value)
        self._inverter: Inverter = inverter
        self.config: dict = config

    async def async_set_value(self, value: float) -> None:
        """Set new value."""
        if self.entity_description.setter:
            await self.entity_description.setter(self._inverter, int(value))
        self._attr_value = value
        self.async_write_ha_state()
