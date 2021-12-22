"""Sensor to collect the reference daily prices of electricity ('PVPC') in Spain."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CURRENCY_EURO, ENERGY_KILO_WATT_HOUR
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ElecPricesDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1
SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="PVPC",
        icon="mdi:currency-eur",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the electricity price sensor from config_entry."""
    coordinator: ElecPricesDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    name = entry.data[CONF_NAME]
    async_add_entities(
        [ElecPriceSensor(coordinator, SENSOR_TYPES[0], entry.unique_id, name)]
    )


class ElecPriceSensor(CoordinatorEntity, SensorEntity):
    """Class to hold the prices of electricity as a sensor."""

    coordinator: ElecPricesDataUpdateCoordinator

    def __init__(
        self,
        coordinator: ElecPricesDataUpdateCoordinator,
        description: SensorEntityDescription,
        unique_id: str | None,
        name: str,
    ) -> None:
        """Initialize ESIOS sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.ree.es/es/apidatos",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.entry_id)},
            manufacturer="REE",
            name="PVPC (REData API)",
        )
        self._state: StateType = None
        self._attrs: Mapping[str, Any] = {}

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        # Update 'state' value in hour changes
        self.async_on_remove(
            async_track_time_change(
                self.hass, self.update_current_price, second=[0], minute=[0]
            )
        )
        _LOGGER.debug(
            "Setup of price sensor %s (%s) with tariff '%s'",
            self.name,
            self.entity_id,
            self.coordinator.api.tariff,
        )

    @callback
    def update_current_price(self, now: datetime) -> None:
        """Update the sensor state, by selecting the current price for this hour."""
        self.coordinator.api.process_state_and_attributes(now)
        self.async_write_ha_state()

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        self._state = self.coordinator.api.state
        return self._state

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        self._attrs = {**self.coordinator.api.attributes}
        return self._attrs
