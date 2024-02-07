"""Support for WireGuard binary sensors."""
from datetime import datetime

from ha_wireguard_api.model import WireGuardPeer

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_LATEST_HANDSHAKE, DOMAIN
from .coordinator import WireGuardUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the WireGuard binary sensors based on a config entry."""
    coordinator: WireGuardUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors: list[WireGuardPeerConnectedSensor] = []
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

    def __init__(self, coordinator: WireGuardUpdateCoordinator, peer_id: str) -> None:
        """Initialize the WireGuard Connected Sensor."""
        super().__init__(coordinator)
        self._peer_id: str = peer_id
        self._attr_name = "Connected"
        self._attr_unique_id = f"{self._peer_id}_connected"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            name=self._peer_id,
            identifiers={(DOMAIN, self._peer_id)},
            configuration_url=self.coordinator.wireguard.host,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._peer_id in self.coordinator.data

    @property
    def peer(self) -> WireGuardPeer:
        """Return peer from coordinator data."""
        return self.coordinator.data[self._peer_id]

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.peer.latest_handshake is not None

    @property
    def extra_state_attributes(self) -> dict[str, datetime | None]:
        """Return the state attributes of the sensor."""
        return {ATTR_LATEST_HANDSHAKE: self.peer.latest_handshake}
