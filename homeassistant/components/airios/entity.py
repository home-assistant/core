"""Base entity for the Airios integration."""

from __future__ import annotations

from pyairios.data_model import AiriosNodeData
from pyairios.registers import ResultStatus

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.exceptions import ConfigEntryNotReady, PlatformNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import AiriosDataUpdateCoordinator


class AiriosEntity(CoordinatorEntity[AiriosDataUpdateCoordinator]):
    """Airios base entity."""

    _attr_has_entity_name = True

    rf_address: int
    slave_id: int

    def __init__(
        self,
        key: str,
        coordinator: AiriosDataUpdateCoordinator,
        node: AiriosNodeData,
        via_config_entry: ConfigEntry | None,
        subentry: ConfigSubentry | None,
    ) -> None:
        """Initialize the entity."""

        super().__init__(coordinator)

        self.slave_id = node["slave_id"]

        if node["rf_address"] is None or node["rf_address"].value is None:
            raise PlatformNotReady("Node RF address not available")
        self.rf_address = node["rf_address"].value

        if node["product_name"] is None or node["product_name"].value is None:
            raise PlatformNotReady("Node product name not available")
        product_name = node["product_name"].value

        if node["product_id"] is None or node["product_id"].value is None:
            raise PlatformNotReady("Node product ID not available")
        product_id = node["product_id"].value

        if node["sw_version"] is None or node["sw_version"].value is None:
            raise PlatformNotReady("Node software version not available")
        sw_version = node["sw_version"].value

        assert self.coordinator.config_entry is not None

        if not product_name:
            product_name = f"0x{self.rf_address:06X}"

        if subentry is None:
            name = product_name
        else:
            name = subentry.data.get("name")
            if name is None:
                raise ConfigEntryNotReady("Failed to get name from subentry")

        self._attr_device_info = DeviceInfo(
            name=name,
            serial_number=f"0x{self.rf_address:06X}",
            identifiers={(DOMAIN, str(self.rf_address))},
            manufacturer=DEFAULT_NAME,
            model=product_name,
            model_id=f"0x{product_id:08X}",
            sw_version=f"0x{sw_version:04X}",
        )

        if via_config_entry is not None:
            if via_config_entry.unique_id is None:
                raise ConfigEntryNotReady("Failed to get config entry unique id")
            self._attr_device_info["via_device"] = (DOMAIN, via_config_entry.unique_id)

        self._attr_unique_id = f"{self.rf_address}-{key}"

    def api(self):
        """Return the Airios API."""
        return self.coordinator.api

    def set_extra_state_attributes_internal(self, status: ResultStatus):
        """Set extra state attributes."""
        self._attr_extra_state_attributes = {
            "age": str(status.age),
            "source": str(status.source),
            "flags": str(status.flags),
        }
