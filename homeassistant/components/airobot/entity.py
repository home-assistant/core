"""Base entities for the Airobot integration."""

from homeassistant.const import CONF_MAC
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AirobotDataUpdateCoordinator, AirobotVUCoordinator


class AirobotEntity(CoordinatorEntity[AirobotDataUpdateCoordinator]):
    """Base class for Airobot entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AirobotDataUpdateCoordinator,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        status = coordinator.data.status
        settings = coordinator.data.settings

        connections = set()
        if (mac := coordinator.config_entry.data.get(CONF_MAC)) is not None:
            connections.add((CONNECTION_NETWORK_MAC, mac))

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, status.device_id)},
            connections=connections,
            name=settings.device_name or status.device_id,
            manufacturer="Airobot",
            model="Thermostat",
            model_id="TE1",
            sw_version=status.fw_version_string,
            hw_version=status.hw_version_string,
        )


class AirobotVUEntity(CoordinatorEntity[AirobotVUCoordinator]):
    """Base class for Airobot ventilation unit entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AirobotVUCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry

        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_{description.key}"

        connections = set()
        if (mac := entry.data.get(CONF_MAC)) is not None:
            connections.add((CONNECTION_NETWORK_MAC, mac))

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            connections=connections,
            name=entry.title,
            manufacturer="Airobot",
            model="Ventilation unit",
            serial_number=(
                coordinator.identity.serial_number if coordinator.identity else None
            ),
            sw_version=str(coordinator.data.firmware_version),
        )
