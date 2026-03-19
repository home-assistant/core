"""BSBLan base entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BSBLanData, get_bsblan_device_info
from .const import DOMAIN
from .coordinator import BSBLanCoordinator, BSBLanFastCoordinator, BSBLanSlowCoordinator


class BSBLanEntityBase[_T: BSBLanCoordinator](CoordinatorEntity[_T]):
    """Base BSBLan entity with common device info setup."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: _T, data: BSBLanData) -> None:
        """Initialize BSBLan entity with device info."""
        super().__init__(coordinator)
        host = coordinator.config_entry.data["host"]
        self._attr_device_info = get_bsblan_device_info(data.device, data.info, host)


class BSBLanEntity(BSBLanEntityBase[BSBLanFastCoordinator]):
    """Defines a base BSBLan entity using the fast coordinator."""

    def __init__(self, coordinator: BSBLanFastCoordinator, data: BSBLanData) -> None:
        """Initialize BSBLan entity."""
        super().__init__(coordinator, data)


class BSBLanCircuitEntity(BSBLanEntity):
    """BSBLan entity belonging to a heating circuit sub-device."""

    def __init__(
        self,
        coordinator: BSBLanFastCoordinator,
        data: BSBLanData,
        circuit: int,
    ) -> None:
        """Initialize BSBLan circuit entity with sub-device info."""
        super().__init__(coordinator, data)
        mac = data.device.MAC
        host = coordinator.config_entry.data["host"]
        main_info = get_bsblan_device_info(data.device, data.info, host)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{mac}-circuit-{circuit}")},
            translation_key=f"heating_circuit_{circuit}",
            via_device=(DOMAIN, mac),
            manufacturer=main_info["manufacturer"],
            model=main_info.get("model"),
            model_id=main_info.get("model_id"),
        )


class BSBLanDualCoordinatorEntity(BSBLanEntity):
    """Entity that listens to both fast and slow coordinators."""

    def __init__(
        self,
        fast_coordinator: BSBLanFastCoordinator,
        slow_coordinator: BSBLanSlowCoordinator,
        data: BSBLanData,
    ) -> None:
        """Initialize BSBLan entity with both coordinators."""
        super().__init__(fast_coordinator, data)
        self.slow_coordinator = slow_coordinator

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Also listen to slow coordinator updates
        self.async_on_remove(
            self.slow_coordinator.async_add_listener(self._handle_coordinator_update)
        )


class BSBLanWaterHeaterDeviceEntity(BSBLanDualCoordinatorEntity):
    """BSBLan entity belonging to the water heater sub-device."""

    def __init__(
        self,
        fast_coordinator: BSBLanFastCoordinator,
        slow_coordinator: BSBLanSlowCoordinator,
        data: BSBLanData,
    ) -> None:
        """Initialize BSBLan water heater sub-device entity."""
        super().__init__(fast_coordinator, slow_coordinator, data)
        mac = data.device.MAC
        host = fast_coordinator.config_entry.data["host"]
        main_info = get_bsblan_device_info(data.device, data.info, host)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{mac}-water-heater")},
            translation_key="water_heater",
            via_device=(DOMAIN, mac),
            manufacturer=main_info["manufacturer"],
            model=main_info.get("model"),
            model_id=main_info.get("model_id"),
        )
