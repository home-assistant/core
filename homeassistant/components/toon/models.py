"""DataUpdate Coordinator, and base Entity and Device models for Toon."""
import logging
from typing import Any, Dict, Optional

from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .coordinator import ToonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class ToonEntity(Entity):
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
        self._enabled_default = enabled_default
        self._icon = icon
        self._name = name
        self._state = None
        self.coordinator = coordinator

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> Optional[str]:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default

    @property
    def should_poll(self) -> bool:
        """Return the polling requirement of the entity."""
        return False

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        """Update Toon entity."""
        await self.coordinator.async_request_refresh()


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
