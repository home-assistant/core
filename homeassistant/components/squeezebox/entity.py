"""Base class for Squeezebox Sensor entities."""

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATUS_QUERY_UUID
from .coordinator import (
    LMSStatusDataUpdateCoordinator,
    SqueezeBoxPlayerUpdateCoordinator,
)


class SqueezeboxEntity(CoordinatorEntity[SqueezeBoxPlayerUpdateCoordinator]):
    """Base entity class for Squeezebox entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SqueezeBoxPlayerUpdateCoordinator) -> None:
        """Initialize the SqueezeBox entity."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._player = self._coordinator.player

        self._manufacturer = None

        if "SqueezeLite" in self._player.model or "SqueezeLite" in self._player.model:
            self._manufacturer = "Ralph Irving & Adrian Smith"
        elif (
            "Squeezebox" in self._player.model
            or "Transporter" in self._player.model
            or "Slim" in self._player.model
            or "Jive" in self._player.model
        ):
            self._manufacturer = "Logitech"
        else:
            match self._player.model:
                case "SqueezePlayer":
                    self._manufacturer = "Stefan Hansel"
                case "Squeezelite-X":
                    self._manufacturer = "R G Dawson"
                case "SqueezeLite-HA-Addon":
                    self._manufacturer = "pssc"
                case "RaopBridge":
                    self._manufacturer = "philippe"
                case "CastBridge":
                    self._manufacturer = "philippe"
                case "SB Player":
                    self._manufacturer = "Wayne Tam"
                case "WiiM Player":
                    self._manufacturer = "LinkPlay"

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
