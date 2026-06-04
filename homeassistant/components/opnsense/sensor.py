"""Sensor platform for OPNsense routers."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .coordinator import OPNsenseDeviceTrackerCoordinator
from .types import DeviceDetails, OPNsenseConfigEntry


@dataclass(frozen=True, kw_only=True)
class OPNsenseSensorDescription(SensorEntityDescription):
    """Description of an OPNsense sensor entity."""

    data_key: str


SENSOR_DESCRIPTIONS: tuple[OPNsenseSensorDescription, ...] = (
    OPNsenseSensorDescription(
        key="expires",
        translation_key="expires",
        data_key="expires",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    ),
    OPNsenseSensorDescription(
        key="interface",
        translation_key="interface",
        data_key="intf_description",
        icon="mdi:lan",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OPNsenseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities for OPNsense."""
    coordinator = entry.runtime_data.coordinator

    @callback
    def _async_add_new_entities() -> None:
        """Add entities for newly discovered devices."""
        if not coordinator.data:
            return

        entities: list[OPNsenseSensorEntity] = []
        for mac_address in coordinator.data:
            for sensor in SENSOR_DESCRIPTIONS:
                unique_id = f"{mac_address}_{sensor.key}"
                if unique_id in coordinator.tracked_devices:
                    continue
                entities.append(
                    OPNsenseSensorEntity(
                        coordinator,
                        mac_address,
                        sensor,
                    )
                )
                coordinator.tracked_devices.add(unique_id)

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))

    _async_add_new_entities()


class OPNsenseSensorEntity(
    CoordinatorEntity[OPNsenseDeviceTrackerCoordinator], SensorEntity
):
    """Representation of an OPNsense sensor for one tracked device."""

    _attr_has_entity_name = True
    entity_description: OPNsenseSensorDescription

    def __init__(
        self,
        coordinator: OPNsenseDeviceTrackerCoordinator,
        mac_address: str,
        description: OPNsenseSensorDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{mac_address}_{description.key}"
        self._mac_address = mac_address
        self._device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, mac_address)}
        )
        if self.available:
            device_data = self.device_data
            if hostname := device_data.get("hostname"):
                self._device_info["default_name"] = str(hostname)
            if manufacturer := device_data.get("manufacturer"):
                self._device_info["default_manufacturer"] = str(manufacturer)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._mac_address in self.coordinator.data

    @property
    def device_info(self) -> DeviceInfo:
        """Return information used to associate entities with a device."""
        return self._device_info

    @property
    def device_data(self) -> DeviceDetails:
        """Return device data for current device."""
        return self.coordinator.data[self._mac_address]

    @property
    def native_value(self) -> datetime | str | None:
        """Return sensor value."""
        device_data = self.device_data
        if not device_data:
            return None

        value = device_data.get(self.entity_description.data_key)
        if value in (None, ""):
            return None

        if self.entity_description.device_class is SensorDeviceClass.TIMESTAMP:
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                return dt_util.parse_datetime(value)
            if isinstance(value, (int, float)):
                return dt_util.utcnow() + timedelta(seconds=value)
            return None

        if isinstance(value, str):
            return value

        return str(value)
