"""Base entity for the Peblar integration."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_HOST
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .coordinator import PeblarConfigEntry


class PeblarEntity[_DataUpdateCoordinatorT: DataUpdateCoordinator[Any]](
    CoordinatorEntity[_DataUpdateCoordinatorT]
):
    """Defines a Peblar entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        entry: PeblarConfigEntry,
        coordinator: _DataUpdateCoordinatorT,
        description: EntityDescription,
    ) -> None:
        """Initialize the Peblar entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"

        system_information = entry.runtime_data.system_information
        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{entry.data[CONF_HOST]}",
            connections={
                (dr.CONNECTION_NETWORK_MAC, system_information.ethernet_mac_address),
                (dr.CONNECTION_NETWORK_MAC, system_information.wlan_mac_address),
            },
            identifiers={
                (DOMAIN, entry.runtime_data.system_information.product_serial_number)
            },
            manufacturer=system_information.product_vendor_name,
            model=system_information.product_model_name,
            model_id=system_information.product_number,
            name="Peblar EV Charger",
            serial_number=system_information.product_serial_number,
            sw_version=entry.runtime_data.version_coordinator.data.current.firmware,
        )
