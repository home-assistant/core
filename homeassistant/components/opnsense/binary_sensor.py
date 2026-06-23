"""Binary sensor platform for OPNsense routers."""

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import OPNsenseConfigEntry, OPNsenseCoordinator
from .types import DeviceDetails


@dataclass(frozen=True, kw_only=True)
class OPNsenseBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Description of an OPNsense binary sensor entity."""

    data_key: str


BINARY_SENSOR_DESCRIPTIONS: tuple[OPNsenseBinarySensorEntityDescription, ...] = (
    OPNsenseBinarySensorEntityDescription(
        key="expired",
        translation_key="expired",
        data_key="expired",
        entity_registry_enabled_default=False,
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

        entities: list[OPNsenseBinarySensorEntity] = []
        for mac_address in coordinator.data:
            for sensor_description in BINARY_SENSOR_DESCRIPTIONS:
                unique_id = f"{mac_address}_{sensor_description.key}"
                if unique_id in coordinator.tracked_devices:
                    continue
                entities.append(
                    OPNsenseBinarySensorEntity(
                        coordinator,
                        mac_address,
                        sensor_description,
                    )
                )
                coordinator.tracked_devices.add(unique_id)

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))

    _async_add_new_entities()


class OPNsenseBinarySensorEntity(
    CoordinatorEntity[OPNsenseCoordinator], BinarySensorEntity
):
    """Representation of an OPNsense binary sensor for one tracked device."""

    _attr_has_entity_name = True
    entity_description: OPNsenseBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: OPNsenseCoordinator,
        mac_address: str,
        description: OPNsenseBinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{mac_address}_{description.key}"
        self._mac_address = mac_address
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, mac_address)}
        )
        if self.available:
            device_data = self.device_data
            if hostname := device_data.get("hostname"):
                self._attr_device_info["default_name"] = str(hostname)
            if manufacturer := device_data.get("manufacturer"):
                self._attr_device_info["default_manufacturer"] = str(manufacturer)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._mac_address in self.coordinator.data

    @property
    def device_data(self) -> DeviceDetails:
        """Return device data for current device."""
        return self.coordinator.data[self._mac_address]

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        if not self.available:
            return False

        device_data = self.device_data

        value = device_data.get(self.entity_description.data_key)
        if value in (None, ""):
            return False

        return bool(value)
