"""DataUpdate Coordinator, and base Entity and Device models for Toon."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ToonDataUpdateCoordinator


class ToonEntity(CoordinatorEntity):
    """Defines a base Toon entity."""

    coordinator: ToonDataUpdateCoordinator


class ToonDisplayDeviceEntity(ToonEntity):
    """Defines a Toon display device entity."""

    @property
    def device_info(self) -> DeviceInfo:
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
    def device_info(self) -> DeviceInfo:
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
    def device_info(self) -> DeviceInfo:
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
    def device_info(self) -> DeviceInfo:
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
    def device_info(self) -> DeviceInfo:
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
    def device_info(self) -> DeviceInfo:
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
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        agreement_id = self.coordinator.data.agreement.agreement_id
        return {
            "name": "Boiler",
            "identifiers": {(DOMAIN, agreement_id, "boiler")},
            "via_device": (DOMAIN, agreement_id, "boiler_module"),
        }


@dataclass
class ToonRequiredKeysMixin:
    """Mixin for required keys."""

    section: str
    measurement: str
