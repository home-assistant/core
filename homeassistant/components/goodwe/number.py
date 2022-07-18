"""GoodWe PV inverter numeric settings entities."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from goodwe import Inverter, InverterError

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, POWER_WATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, KEY_DEVICE_INFO, KEY_INVERTER

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


NUMBERS = (
    GoodweNumberEntityDescription(
        key="grid_export_limit",
        name="Grid export limit",
        icon="mdi:transmission-tower",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=POWER_WATT,
        getter=lambda inv: inv.get_grid_export_limit(),
        setter=lambda inv, val: inv.set_grid_export_limit(val),
        native_step=100,
        native_min_value=0,
        native_max_value=10000,
    ),
    GoodweNumberEntityDescription(
        key="battery_discharge_depth",
        name="Depth of discharge (on-grid)",
        icon="mdi:battery-arrow-down",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        getter=lambda inv: inv.get_ongrid_battery_dod(),
        setter=lambda inv, val: inv.set_ongrid_battery_dod(val),
        native_step=1,
        native_min_value=0,
        native_max_value=99,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the inverter select entities from a config entry."""
    inverter = hass.data[DOMAIN][config_entry.entry_id][KEY_INVERTER]
    device_info = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE_INFO]

    entities = []

    for description in NUMBERS:
        try:
            current_value = await description.getter(inverter)
        except (InverterError, ValueError):
            # Inverter model does not support this setting
            _LOGGER.debug("Could not read inverter setting %s", description.key)
            continue

        entities.append(
            InverterNumberEntity(device_info, description, inverter, current_value),
        )

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
    ) -> None:
        """Initialize the number inverter setting entity."""
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}-{description.key}-{inverter.serial_number}"
        self._attr_device_info = device_info
        self._attr_native_value = float(current_value)
        self._inverter: Inverter = inverter

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if self.entity_description.setter:
            await self.entity_description.setter(self._inverter, int(value))
        self._attr_native_value = value
        self.async_write_ha_state()
