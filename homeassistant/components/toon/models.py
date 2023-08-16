"""DataUpdate Coordinator, and base Entity and Device models for Toon."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ToonDataUpdateCoordinator


class ToonEntity(CoordinatorEntity[ToonDataUpdateCoordinator]):
    """Defines a base Toon entity."""


class ToonDisplayDeviceEntity(ToonEntity):
    """Defines a Toon display device entity."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this thermostat."""
        agreement = self.coordinator.data.agreement
        return DeviceInfo(
            identifiers={(DOMAIN, agreement.agreement_id)},
            manufacturer="Eneco",
            model=agreement.display_hardware_version.rpartition("/")[0],
            name="Toon Display",
            sw_version=agreement.display_software_version.rpartition("/")[-1],
        )


class ToonElectricityMeterDeviceEntity(ToonEntity):
    """Defines a Electricity Meter device entity."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        agreement_id = self.coordinator.data.agreement.agreement_id
        return DeviceInfo(
            name="Electricity Meter",
            identifiers={
                (DOMAIN, agreement_id, "electricity"),  # type: ignore[arg-type]
            },
            via_device=(
                DOMAIN,
                agreement_id,  # type: ignore[typeddict-item]
                "meter_adapter",
            ),
        )


class ToonGasMeterDeviceEntity(ToonEntity):
    """Defines a Gas Meter device entity."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        agreement_id = self.coordinator.data.agreement.agreement_id
        return DeviceInfo(
            name="Gas Meter",
            identifiers={
                (DOMAIN, agreement_id, "gas"),  # type: ignore[arg-type]
            },
            via_device=(
                DOMAIN,
                agreement_id,  # type: ignore[typeddict-item]
                "electricity",
            ),
        )


class ToonWaterMeterDeviceEntity(ToonEntity):
    """Defines a Water Meter device entity."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        agreement_id = self.coordinator.data.agreement.agreement_id
        return DeviceInfo(
            name="Water Meter",
            identifiers={
                (DOMAIN, agreement_id, "water"),  # type: ignore[arg-type]
            },
            via_device=(
                DOMAIN,
                agreement_id,  # type: ignore[typeddict-item]
                "electricity",
            ),
        )


class ToonSolarDeviceEntity(ToonEntity):
    """Defines a Solar Device device entity."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        agreement_id = self.coordinator.data.agreement.agreement_id
        return DeviceInfo(
            name="Solar Panels",
            identifiers={
                (DOMAIN, agreement_id, "solar"),  # type: ignore[arg-type]
            },
            via_device=(
                DOMAIN,
                agreement_id,  # type: ignore[typeddict-item]
                "meter_adapter",
            ),
        )


class ToonBoilerModuleDeviceEntity(ToonEntity):
    """Defines a Boiler Module device entity."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        agreement_id = self.coordinator.data.agreement.agreement_id
        return DeviceInfo(
            name="Boiler Module",
            manufacturer="Eneco",
            identifiers={
                (
                    DOMAIN,
                    agreement_id,  # type: ignore[arg-type]
                    "boiler_module",
                )
            },
            via_device=(DOMAIN, agreement_id),
        )


class ToonBoilerDeviceEntity(ToonEntity):
    """Defines a Boiler device entity."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        agreement_id = self.coordinator.data.agreement.agreement_id
        return DeviceInfo(
            name="Boiler",
            identifiers={
                (DOMAIN, agreement_id, "boiler"),  # type: ignore[arg-type]
            },
            via_device=(
                DOMAIN,
                agreement_id,  # type: ignore[typeddict-item]
                "boiler_module",
            ),
        )


@dataclass
class ToonRequiredKeysMixin:
    """Mixin for required keys."""

    section: str
    measurement: str
