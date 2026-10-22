"""Base entity class for the NeoPool integration."""

from typing import override

from neopool_modbus.decoders import get_machine_name, parse_version

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import NeoPoolCoordinator


class NeoPoolEntity(CoordinatorEntity[NeoPoolCoordinator]):
    """Base class for NeoPool entities."""

    _attr_has_entity_name = True

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device information for the entity."""
        data = self.coordinator.data or {}
        unique_id = self.coordinator.config_entry.unique_id
        assert unique_id is not None
        machine_type = (get_machine_name(data) or "").strip()
        model_prefix = "NeoPool Compatible: " if machine_type else "NeoPool Compatible"

        return DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=NAME,
            model=f"{model_prefix}{machine_type}".strip(),
            manufacturer="Hayward (Sugar Valley)",
            sw_version=f"v{parse_version(data.get('MBF_POWER_MODULE_VERSION'))} (v{parse_version(data.get('MBF_PAR_VERSION'))})",
            serial_number=unique_id,
        )
