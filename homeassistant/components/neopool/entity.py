"""Base entity class for the NeoPool integration."""

from typing import override

from neopool_modbus.decoders import (
    decode_par_model_modules,
    get_machine_name,
    modbus_regs_to_hex_string,
    parse_version,
)

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify as ha_slugify

from .const import DOMAIN, NAME
from .coordinator import NeoPoolCoordinator

_MODULE_LABELS: dict[str, str] = {
    "ionization": "Ionization",
    "hydrolysis": "Hydro/Electrolysis",
    "uv_lamp": "UV Lamp",
    "salinity": "Salinity",
}


class NeoPoolEntity(CoordinatorEntity[NeoPoolCoordinator]):
    """Base class for NeoPool entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NeoPoolCoordinator, entry_id: str) -> None:
        """Initialise the NeoPool base entity."""
        super().__init__(coordinator)
        self._entry_id = entry_id

    @property
    @override
    def translation_key(self) -> str | None:
        """Return the translation key for the entity."""
        return getattr(self, "_attr_translation_key", None)  # pragma: no cover

    @property
    @override
    def device_info(self) -> DeviceInfo:  # pragma: no cover
        """Return device information for the entity."""
        data = self.coordinator.data or {}
        serial_number = modbus_regs_to_hex_string(data.get("MBF_POWER_MODULE_NODEID"))

        hw_identifier = self.coordinator.entry.unique_id or self._entry_id

        machine_type = (get_machine_name(data) or "").strip()
        model_prefix = "NeoPool Compatible: " if machine_type else "NeoPool Compatible"

        return DeviceInfo(
            identifiers={(DOMAIN, hw_identifier)},
            name=getattr(self.coordinator, "device_name", NAME),
            model=f"{model_prefix}{machine_type}".strip(),
            manufacturer="Hayward (Sugar Valley)",
            hw_version=f"Detected Modules: [{self._format_modules(data)}]",
            sw_version=f"v{self.coordinator.firmware} (v{parse_version(data.get('MBF_PAR_VERSION'))})",
            serial_number=serial_number,
        )

    @staticmethod
    def slugify(name: str) -> str:
        """Convert a name to a slug suitable for use as an object ID."""
        if not name:
            return ""
        return ha_slugify(name.lower().replace("mbf_", "", 1).replace("par_", "", 1))

    @staticmethod
    def _format_modules(data: dict) -> str:
        """Render installed_modules as the hw_version label."""
        modules = data.get("installed_modules")
        if modules is None:
            # Coordinator data not yet populated.
            modules = decode_par_model_modules(data.get("MBF_PAR_MODEL"))
        if not modules:
            return "None" if data.get("MBF_PAR_MODEL") is not None else "Unknown"
        return ", ".join(_MODULE_LABELS.get(m, m) for m in modules)
