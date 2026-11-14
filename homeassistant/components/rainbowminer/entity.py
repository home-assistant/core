"""Common entity for the RainbowMiner integration."""

from yarl import URL

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
        entry = coordinator.config_entry
        host = entry.data[CONF_HOST]
        port = entry.data.get(CONF_PORT, DEFAULT_PORT)
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="RainbowMiner",
            name="RainbowMiner",
            sw_version=coordinator.data.version.version_string(),
            configuration_url=str(URL.build(scheme="http", host=host, port=port)),
        )
