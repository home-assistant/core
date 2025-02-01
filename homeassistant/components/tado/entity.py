"""Base class for Tado entity."""

import logging

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN, TADO_HOME, TADO_ZONE
from .coordinator import TadoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class TadoCoordinatorEntity(CoordinatorEntity[TadoDataUpdateCoordinator]):
    """Base class for Tado entity."""

    _attr_has_entity_name = True


class TadoDeviceEntity(TadoCoordinatorEntity):
    """Base implementation for Tado device."""

    def __init__(
        self, device_info: dict[str, str], coordinator: TadoDataUpdateCoordinator
    ) -> None:
        """Initialize a Tado device."""
        super().__init__(coordinator)
        self._device_info = device_info
        self.device_name = device_info["serialNo"]
        self.device_id = device_info["shortSerialNo"]
        self._attr_device_info = DeviceInfo(
            configuration_url=f"https://app.tado.com/en/main/settings/rooms-and-devices/device/{self.device_name}",
            identifiers={(DOMAIN, self.device_id)},
            name=self.device_name,
            manufacturer=DEFAULT_NAME,
            sw_version=device_info["currentFwVersion"],
            model=device_info["deviceType"],
            via_device=(DOMAIN, device_info["serialNo"]),
        )


class TadoHomeEntity(TadoCoordinatorEntity):
    """Base implementation for Tado home."""

    def __init__(self, coordinator: TadoDataUpdateCoordinator) -> None:
        """Initialize a Tado home."""
        super().__init__(coordinator)
        self.home_name = coordinator.home_name
        self.home_id = coordinator.home_id
        self._attr_device_info = DeviceInfo(
            configuration_url="https://app.tado.com",
            identifiers={(DOMAIN, str(coordinator.home_id))},
            manufacturer=DEFAULT_NAME,
            model=TADO_HOME,
            name=coordinator.home_name,
        )


class TadoZoneEntity(TadoCoordinatorEntity):
    """Base implementation for Tado zone."""

    def __init__(
        self,
        zone_name: str,
        home_id: int,
        zone_id: int,
        coordinator: TadoDataUpdateCoordinator,
    ) -> None:
        """Initialize a Tado zone."""
        super().__init__(coordinator)
        self.zone_name = zone_name
        self.zone_id = zone_id
        self._attr_device_info = DeviceInfo(
            configuration_url=(f"https://app.tado.com/en/main/home/zoneV2/{zone_id}"),
            identifiers={(DOMAIN, f"{home_id}_{zone_id}")},
            name=zone_name,
            manufacturer=DEFAULT_NAME,
            model=TADO_ZONE,
            suggested_area=zone_name,
        )
