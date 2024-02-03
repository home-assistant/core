"""Support for WireGuard binary sensors."""
from datetime import datetime

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import WireGuardPeer
from .const import ATTR_LATEST_HANDSHAKE, DOMAIN
from .coordinator import WireGuardUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the WireGuard binary sensors based on a config entry."""
    coordinator: WireGuardUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors: list[Entity] = []
    sensors.extend(
        WireGuardPeerConnectedSensor(coordinator, peer) for peer in coordinator.data
    )
    async_add_entities(sensors)


class WireGuardPeerConnectedSensor(
    CoordinatorEntity[WireGuardUpdateCoordinator], BinarySensorEntity
):
    """Representation of a WireGuard connection status."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: WireGuardUpdateCoordinator, peer: WireGuardPeer
    ) -> None:
        """Initialize the WireGuard Connected Sensor."""
        super().__init__(coordinator)
        self.peer: WireGuardPeer = peer
        self._attr_unique_id = f"{self.peer.name}_connected"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            name=self.peer.name,
            identifiers={(DOMAIN, self.peer.name)},
            configuration_url=self.coordinator.wireguard.host,
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.peer.latest_handshake is not None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.peer.name in [
            peer.name for peer in self.coordinator.data
        ]

    @property
    def extra_state_attributes(self) -> dict[str, datetime | None]:
        """Return the state attributes of the sensor."""
        return {ATTR_LATEST_HANDSHAKE: self.peer.latest_handshake}
