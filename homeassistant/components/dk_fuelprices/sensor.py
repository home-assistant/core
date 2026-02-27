"""Sensor platform for dk_fuelprices integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify as util_slugify

from . import DkFuelpricesConfigEntry
from .const import DOMAIN
from .coordinator import APIClient

SENSORS = [
    SensorEntityDescription(
        key="price",
        name="Fuel Price",
        native_unit_of_measurement="DKK/L",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:gas-station",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DkFuelpricesConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor platform for Braendstofpriser integration."""

    for coordinator in entry.runtime_data.values():
        expected_unique_ids = set()
        for product_key in coordinator.products:
            expected_unique_ids.add(
                util_slugify(f"{coordinator.subentry_id}_price_{product_key}")
            )

        ent_reg = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
            if entity.config_subentry_id != coordinator.subentry_id:
                continue
            if entity.unique_id and entity.unique_id not in expected_unique_ids:
                ent_reg.async_remove(entity.entity_id)
        dev_reg = dr.async_get(hass)
        for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
            if (DOMAIN, coordinator.subentry_id) not in device.identifiers:
                continue
            if not er.async_entries_for_device(ent_reg, device.id):
                dev_reg.async_remove_device(device.id)

        subentry_sensors = []
        for sensor in SENSORS:
            for product_key, product_info in coordinator.products.items():
                product_name = product_info["name"]
                subentry_sensors.append(
                    BraendstofpriserSensor(
                        coordinator,
                        product_key,
                        product_name if isinstance(product_name, str) else product_key,
                        sensor,
                    )
                )

        async_add_devices(
            subentry_sensors,
            True,
            config_subentry_id=coordinator.subentry_id,
        )


class BraendstofpriserSensor(CoordinatorEntity[APIClient], RestoreSensor):
    """Sensor for Braendstofpriser integration."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: APIClient,
        product_key: str,
        product_name: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._product_key = product_key
        self._product_name = product_name

        self._attr_name = f"{product_name}"

        self._attr_unique_id = util_slugify(
            f"{self.coordinator.subentry_id}_{self.entity_description.key}_{product_key}"
        )
        self._attr_config_subentry_id = self.coordinator.subentry_id

        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    self.coordinator.subentry_id,
                )
            },
            name=self.coordinator.station_name,
            manufacturer=self.coordinator.company,
            model=self.coordinator.station_name,
        )

        self._attr_native_value = self.get_value()

    def get_value(self) -> float | None:
        """Get the current value of the sensor."""
        if (product := self.coordinator.products.get(self._product_key)) is None:
            return None

        if isinstance(price := product.get("price"), int | float):
            return float(price)

        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        value = self.get_value()

        if value is not None:
            self._attr_native_value = self.get_value()

        self.schedule_update_ha_state()
