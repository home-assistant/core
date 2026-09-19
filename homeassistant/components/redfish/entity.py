"""Shared entities for Redfish."""

from typing import override

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import RedfishAuthError, RedfishError
from .const import DOMAIN
from .coordinator import RedfishDataUpdateCoordinator
from .models import RedfishSystem


class RedfishSystemEntity(CoordinatorEntity[RedfishDataUpdateCoordinator]):
    """Base entity for a Redfish ComputerSystem."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: RedfishDataUpdateCoordinator, system_id: str
    ) -> None:
        """Initialize a system entity."""
        super().__init__(coordinator)
        self._system_id = system_id
        system = coordinator.data.systems[system_id]
        assert coordinator.config_entry.unique_id is not None
        self._system_identity = (
            f"{coordinator.config_entry.unique_id}_{system.system_id}"
        )
        identifiers = {(DOMAIN, self._system_identity)}
        if system.uuid is not None:
            identifiers.add((DOMAIN, system.uuid))
        self._attr_device_info = DeviceInfo(
            identifiers=identifiers,
            name=system.name or system.system_id,
            manufacturer=system.manufacturer,
            model=system.model,
            serial_number=system.serial_number,
        )

    @property
    def system(self) -> RedfishSystem | None:
        """Return current system data."""
        return self.coordinator.data.systems.get(self._system_id)

    @property
    @override
    def available(self) -> bool:
        """Return whether this system is present in the latest update."""
        return super().available and self.system is not None

    async def _async_reset(self, reset_type: str) -> None:
        """Issue a reset type only when currently advertised."""
        system = self.system
        if (
            system is None
            or system.reset_target is None
            or reset_type not in system.reset_types
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="reset_not_supported",
                translation_placeholders={"reset_type": reset_type},
            )
        try:
            await self.coordinator.client.async_reset(system.reset_target, reset_type)
        except RedfishAuthError as err:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except RedfishError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="reset_failed",
                translation_placeholders={"reset_type": reset_type},
            ) from err
        await self.coordinator.async_request_refresh()
