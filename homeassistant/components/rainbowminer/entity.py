"""Common entity for the RainbowMiner integration."""

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_PORT, DOMAIN
from .coordinator import RainbowMinerCoordinator


class RainbowMinerEntity(CoordinatorEntity[RainbowMinerCoordinator]):
    """Base entity for RainbowMiner."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RainbowMinerCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        host = coordinator.config_entry.data[CONF_HOST]
        port = coordinator.config_entry.data.get(CONF_PORT, DEFAULT_PORT)
        self._attr_unique_id = f"{host}:{port}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host}:{port}")},
            manufacturer="RainbowMiner",
            name="RainbowMiner",
            configuration_url=f"http://{host}:{port}",
        )
