"""Base class for Squeezebox Sensor entities."""

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATUS_QUERY_UUID
from .coordinator import (
    LMSStatusDataUpdateCoordinator,
    SqueezeBoxPlayerUpdateCoordinator,
)


class SqueezeboxEntity(Entity):
    """Base entity class for Squeezebox entities."""

    def __init__(self, coordinator: SqueezeBoxPlayerUpdateCoordinator) -> None:
        """Initialize the SqueezeBox entity."""
        self._coordinator = coordinator
        self._player = self._coordinator.player
        self._attr_has_entity_name = True
        self._manufacturer = None
        if (
            self._player.model.startswith("SqueezeLite")
            or "SqueezePlay" in self._player.model
        ):
            self._manufacturer = "Ralph Irving"
        elif (
            "Squeezebox" in self._player.model
            or "Transporter" in self._player.model
            or "Slim" in self._player.model
        ):
            self._manufacturer = "Logitech"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, format_mac(self._player.player_id))},
            name=self._player.name,
            connections={(CONNECTION_NETWORK_MAC, format_mac(self._player.player_id))},
            via_device=(DOMAIN, self._coordinator.server_uuid),
            model=self._player.model,
            manufacturer=self._manufacturer,
        )


class LMSStatusEntity(CoordinatorEntity[LMSStatusDataUpdateCoordinator]):
    """Defines a base status sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LMSStatusDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize status sensor entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_translation_key = description.key.replace(" ", "_")
        self._attr_unique_id = (
            f"{coordinator.data[STATUS_QUERY_UUID]}_{description.key}"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data[STATUS_QUERY_UUID])},
        )
