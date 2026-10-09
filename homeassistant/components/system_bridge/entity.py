"""Base entity for the system bridge integration."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SystemBridgeDataUpdateCoordinator


class SystemBridgeEntity(CoordinatorEntity[SystemBridgeDataUpdateCoordinator]):
    """Defines a base System Bridge entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        api_port: int,
        key: str | None = None,
    ) -> None:
        """Initialize the System Bridge entity."""
        super().__init__(coordinator)

        system = coordinator.data.system
        assert system is not None

        self._hostname = system.hostname
        self._attr_unique_id = (
            f"{system.uuid}_{key}" if key is not None else system.uuid
        )
        self._configuration_url = (
            f"http://{self._hostname}:{api_port}/app/settings.html"
        )
        self._mac_address = system.mac_address
        self._uuid = system.uuid
        self._version = system.version

        self._attr_device_info = DeviceInfo(
            configuration_url=self._configuration_url,
            connections={(dr.CONNECTION_NETWORK_MAC, self._mac_address)},
            identifiers={(DOMAIN, self._uuid)},
            name=self._hostname,
            sw_version=self._version,
        )
