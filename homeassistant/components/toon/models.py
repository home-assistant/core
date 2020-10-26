"""DataUpdate Coordinator, and base Entity and Device models for Toon."""
from typing import Any, Dict, Optional

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ToonDataUpdateCoordinator


class ToonEntity(CoordinatorEntity):
    """Defines a base Toon entity."""

    def __init__(
        self,
        coordinator: ToonDataUpdateCoordinator,
        *,
        name: str,
        icon: str,
        enabled_default: bool = True,
    ) -> None:
        """Initialize the Toon entity."""
        super().__init__(coordinator)
        self._enabled_default = enabled_default
        self._icon = icon
        self._name = name
        self._state = None

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> Optional[str]:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default


class ToonDisplayDeviceEntity(ToonEntity):
    """Defines a Toon display device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this thermostat."""
        agreement = self.coordinator.data.agreement
        model = agreement.display_hardware_version.rpartition("/")[0]
        sw_version = agreement.display_software_version.rpartition("/")[-1]
        return {
            "identifiers": {(DOMAIN, agreement.agreement_id)},
            "name": "Toon Display",
            "manufacturer": "Eneco",
            "model": model,
            "sw_version": sw_version,
        }


class ToonElectricityMeterDeviceEntity(ToonEntity):
    """Defines a Electricity Meter device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        agreement_id = self.coordinator.data.agreement.agreement_id
        return {
            "name": "Electricity Meter",
            "identifiers": {(DOMAIN, agreement_id, "electricity")},
            "via_device": (DOMAIN, agreement_id, "meter_adapter"),
        }


class ToonGasMeterDeviceEntity(ToonEntity):
    """Defines a Gas Meter device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        agreement_id = self.coordinator.data.agreement.agreement_id
        return {
            "name": "Gas Meter",
            "identifiers": {(DOMAIN, agreement_id, "gas")},
            "via_device": (DOMAIN, agreement_id, "electricity"),
        }


class ToonWaterMeterDeviceEntity(ToonEntity):
    """Defines a Water Meter device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        agreement_id = self.coordinator.data.agreement.agreement_id
        return {
            "name": "Water Meter",
            "identifiers": {(DOMAIN, agreement_id, "water")},
            "via_device": (DOMAIN, agreement_id, "electricity"),
        }


class ToonSolarDeviceEntity(ToonEntity):
    """Defines a Solar Device device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        agreement_id = self.coordinator.data.agreement.agreement_id
        return {
            "name": "Solar Panels",
            "identifiers": {(DOMAIN, agreement_id, "solar")},
            "via_device": (DOMAIN, agreement_id, "meter_adapter"),
        }


class ToonBoilerModuleDeviceEntity(ToonEntity):
    """Defines a Boiler Module device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        agreement_id = self.coordinator.data.agreement.agreement_id
        return {
            "name": "Boiler Module",
            "manufacturer": "Eneco",
            "identifiers": {(DOMAIN, agreement_id, "boiler_module")},
            "via_device": (DOMAIN, agreement_id),
        }


class ToonBoilerDeviceEntity(ToonEntity):
    """Defines a Boiler device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        agreement_id = self.coordinator.data.agreement.agreement_id
        return {
            "name": "Boiler",
            "identifiers": {(DOMAIN, agreement_id, "boiler")},
            "via_device": (DOMAIN, agreement_id, "boiler_module"),
        }
