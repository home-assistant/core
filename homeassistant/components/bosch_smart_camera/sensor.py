"""Sensor platform for the Bosch Smart Camera integration."""

from typing import override

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BoschCameraConfigEntry, BoschWifiCoordinator

PARALLEL_UPDATES = 0

WIFI_SIGNAL_STRENGTH = SensorEntityDescription(
    key="wifi_signal_strength",
    translation_key="wifi_signal_strength",
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoschCameraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors of the cameras."""
    cameras = entry.runtime_data
    coordinator = BoschWifiCoordinator(hass, entry, cameras)
    await coordinator.async_refresh()
    known: set[str] = set()

    @callback
    def _add_new_sensors() -> None:
        # Forget removed cameras so one that comes back gets a new entity.
        known.intersection_update(cameras.data)
        new = set(cameras.data) - known
        known.update(new)
        async_add_entities(
            BoschWifiSensor(coordinator, camera_id, cameras.data[camera_id].title)
            for camera_id in new
        )

    entry.async_on_unload(cameras.async_add_listener(_add_new_sensors))
    _add_new_sensors()


class BoschWifiSensor(CoordinatorEntity[BoschWifiCoordinator], SensorEntity):
    """The Wi-Fi signal strength of a camera."""

    _attr_has_entity_name = True
    entity_description = WIFI_SIGNAL_STRENGTH

    def __init__(
        self, coordinator: BoschWifiCoordinator, camera_id: str, title: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._camera_id = camera_id
        self._attr_unique_id = f"{camera_id}_{self.entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, camera_id)}, manufacturer="Bosch", name=title
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the last poll returned a value for this camera."""
        return super().available and self._camera_id in self.coordinator.data

    @property
    @override
    def native_value(self) -> int | None:
        """Return the signal strength in percent."""
        return self.coordinator.data.get(self._camera_id)
