"""Binary sensors for Meraki Dashboard infrastructure devices."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    MerakiDashboardConfigEntry,
    MerakiDashboardDataUpdateCoordinator,
    MerakiDashboardInfrastructureDevice,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MerakiDashboardConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Meraki Dashboard infrastructure device entities."""
    coordinator = config_entry.runtime_data
    tracked_serials: set[str] = set()

    @callback
    def async_add_new_entities() -> None:
        latest_devices = set(coordinator.data.infrastructure_devices)
        entities = [
            MerakiDashboardDeviceStatusBinarySensor(coordinator, serial)
            for serial in latest_devices - tracked_serials
        ]

        tracked_serials.update(latest_devices)
        if entities:
            async_add_entities(entities)

    async_add_new_entities()
    config_entry.async_on_unload(coordinator.async_add_listener(async_add_new_entities))


class MerakiDashboardDeviceStatusBinarySensor(
    CoordinatorEntity[MerakiDashboardDataUpdateCoordinator], BinarySensorEntity
):
    """Representation of a Meraki infrastructure device status."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: MerakiDashboardDataUpdateCoordinator, serial: str
    ) -> None:
        """Initialize the infrastructure status entity."""
        super().__init__(coordinator)
        self._serial = serial
        self._attr_unique_id = f"{serial}_connectivity"

    @property
    def _device(self) -> MerakiDashboardInfrastructureDevice | None:
        """Return device data."""
        return self.coordinator.data.infrastructure_devices.get(self._serial)

    @property
    def name(self) -> str:
        """Return name of the entity."""
        if (device := self._device) is None:
            return self._serial
        return device.name or device.serial

    @property
    def is_on(self) -> bool:
        """Return true if device is currently connected."""
        return self._device is not None and self._device.status == "online"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information for the infrastructure device."""
        if (device := self._device) is None:
            return None
        connections = set()
        if device.mac:
            connections.add((CONNECTION_NETWORK_MAC, device.mac))
        return DeviceInfo(
            identifiers={(DOMAIN, device.serial)},
            connections=connections,
            manufacturer="Cisco Meraki",
            model=device.model,
            name=device.name or device.serial,
        )

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return extra state attributes."""
        return {}
