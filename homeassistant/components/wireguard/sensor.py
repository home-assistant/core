"""Support for WireGuard binary sensors."""
from datetime import datetime

from ha_wireguard_api.model import WireGuardPeer

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WireGuardUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the WireGuard sensors based on a config entry."""
    coordinator: WireGuardUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    sensors: list[SensorEntity] = []
    sensors.extend(
        WireGuardPeerHandshakeSensor(coordinator, peer) for peer in coordinator.data
    )
    sensors.extend(
        WireGuardPeerBytesReceivedSensor(coordinator, peer) for peer in coordinator.data
    )
    sensors.extend(
        WireGuardPeerBytesSentSensor(coordinator, peer) for peer in coordinator.data
    )
    async_add_entities(sensors)


class WireGuardPeerHandshakeSensor(
    CoordinatorEntity[WireGuardUpdateCoordinator], SensorEntity
):
    """Representation of a WireGuard latest_handshake status."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_has_entity_name = True

    def __init__(self, coordinator: WireGuardUpdateCoordinator, peer_id: str) -> None:
        """Initialize the WireGuard latest_handshake Sensor."""
        super().__init__(coordinator)
        self._peer_id: str = peer_id
        self._attr_translation_key = "latest_handshake"
        self._attr_unique_id = f"{self._peer_id}_latest_handshake"
        self._latest_handshake: datetime | None = None

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

    @callback
    def _handle_coordinator_update(self):
        """Handle update of self._latest_handshake."""
        if latest_handshake := self.peer.latest_handshake:
            self._latest_handshake = latest_handshake
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> datetime | None:
        """Return the state of the sensor."""
        return self._latest_handshake


class WireGuardPeerBytesReceivedSensor(
    CoordinatorEntity[WireGuardUpdateCoordinator], SensorEntity
):
    """Representation of a WireGuard Bytes Received status."""

    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_has_entity_name = True

    def __init__(self, coordinator: WireGuardUpdateCoordinator, peer_id: str) -> None:
        """Initialize the WireGuard Bytes Received Sensor."""
        super().__init__(coordinator)
        self._peer_id: str = peer_id
        self._attr_translation_key = "received"
        self._attr_unique_id = f"{self._peer_id}_transfer_rx"
        self._attr_native_unit_of_measurement = UnitOfInformation.BYTES
        self._attr_suggested_unit_of_measurement = UnitOfInformation.MEGABYTES
        self._attr_suggested_display_precision = 2

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
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.peer.transfer_rx


class WireGuardPeerBytesSentSensor(
    CoordinatorEntity[WireGuardUpdateCoordinator], SensorEntity
):
    """Representation of a WireGuard Bytes Received status."""

    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_has_entity_name = True

    def __init__(self, coordinator: WireGuardUpdateCoordinator, peer_id: str) -> None:
        """Initialize the WireGuard Bytes Received Sensor."""
        super().__init__(coordinator)
        self._peer_id: str = peer_id
        self._attr_translation_key = "sent"
        self._attr_unique_id = f"{self._peer_id}_transfer_tx"
        self._attr_native_unit_of_measurement = UnitOfInformation.BYTES
        self._attr_suggested_unit_of_measurement = UnitOfInformation.MEGABYTES
        self._attr_suggested_display_precision = 2

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
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.peer.transfer_tx
