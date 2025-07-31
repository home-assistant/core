"""Support for Hinen Sensors."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import AUTH, COORDINATOR, DOMAIN
from .coordinator import HinenDataUpdateCoordinator
from .entity import HinenDeviceEntity
from .hinen import HinenOpen

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=False)
class HinenNumberEntityDescription(NumberEntityDescription):
    """Describes Hinen number entity."""


NUMBER_TYPES = [
    HinenNumberEntityDescription(
        key="load_first_stop_soc",
        translation_key="load_first_stop_soc",
        entity_category=EntityCategory.CONFIG,
        native_min_value=10,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
    ),
    HinenNumberEntityDescription(
        key="charge_stop_soc",
        translation_key="charge_stop_soc",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
    ),
    HinenNumberEntityDescription(
        key="grid_first_stop_soc",
        translation_key="grid_first_stop_soc",
        entity_category=EntityCategory.CONFIG,
        native_min_value=10,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
    ),
    HinenNumberEntityDescription(
        key="charge_power_set",
        translation_key="charge_power_set",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=655340,
        native_step=10,
        native_unit_of_measurement="W",
    ),
    HinenNumberEntityDescription(
        key="discharge_power_set",
        translation_key="discharge_power_set",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=655340,
        native_step=10,
        native_unit_of_measurement="W",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hinen number."""
    coordinator: HinenDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]
    hinen_open: HinenOpen = hass.data[DOMAIN][entry.entry_id][AUTH].hinen_open

    entities: list = [
        HinenLoadFirstStopSOCNumber(coordinator, hinen_open, sensor_type, device_id)
        for device_id in coordinator.data
        for sensor_type in NUMBER_TYPES
    ]

    async_add_entities(entities)


class HinenLoadFirstStopSOCNumber(HinenDeviceEntity, NumberEntity):
    """Representation of a Hinen load first stop SOC number."""

    entity_description: HinenNumberEntityDescription

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return True

    @property
    def native_value(self) -> int | None:
        """Return the current load first stop SOC."""
        if not self.coordinator.data:
            return None
        attr_load_first_stop_soc = self.coordinator.data[self._device_id][
            self.entity_description.key
        ]
        _LOGGER.debug("current native_value: %s", attr_load_first_stop_soc)
        return attr_load_first_stop_soc

    async def async_set_native_value(self, value: float) -> None:
        """Set the current load first stop SOC."""
        _LOGGER.debug("set native_value: %s", value)
        if value is not None:
            await self.hinen_open.set_property(
                int(value), self._device_id, self.entity_description.key
            )
            self.coordinator.data[self._device_id][self.entity_description.key] = value
            self.async_write_ha_state()
