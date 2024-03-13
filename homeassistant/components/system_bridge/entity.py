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
        key: str,
    ) -> None:
        """Initialize the System Bridge entity."""
        super().__init__(coordinator)

        self._hostname = coordinator.data.system.hostname
        self._key = f"{self._hostname}_{key}"
        self._configuration_url = (
            f"http://{self._hostname}:{api_port}/app/settings.html"
        )
        self._mac_address = coordinator.data.system.mac_address
        self._uuid = coordinator.data.system.uuid
        self._version = coordinator.data.system.version

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return self._key

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this System Bridge instance."""
        return DeviceInfo(
            configuration_url=self._configuration_url,
            connections={(dr.CONNECTION_NETWORK_MAC, self._mac_address)},
            identifiers={(DOMAIN, self._uuid)},
            name=self._hostname,
            sw_version=self._version,
        )
