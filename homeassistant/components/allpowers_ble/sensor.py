"""Allpowers BLE integration sensor platform."""


from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AllpowersBLE, AllpowersBLECoordinator
from .const import DOMAIN
from .models import AllpowersBLEData

WATTS_EXPORT_DESCRIPTION = SensorEntityDescription(
    key="watts_export",
    translation_key="watts_export",
    device_class=SensorDeviceClass.POWER,
    entity_registry_enabled_default=False,
    entity_registry_visible_default=True,
    native_unit_of_measurement=UnitOfPower.WATT,
    state_class=SensorStateClass.MEASUREMENT,
    name="Power Export",
)

WATTS_IMPORT_DESCRIPTION = SensorEntityDescription(
    key="watts_import",
    translation_key="watts_import",
    device_class=SensorDeviceClass.POWER,
    entity_registry_enabled_default=False,
    entity_registry_visible_default=True,
    native_unit_of_measurement=UnitOfPower.WATT,
    state_class=SensorStateClass.MEASUREMENT,
    name="Power Import",
)


MINUTES_REMAINING_DESCRIPTION = SensorEntityDescription(
    key="minutes_remain",
    translation_key="minutes_remain",
    device_class=SensorDeviceClass.BATTERY,
    entity_registry_enabled_default=False,
    entity_registry_visible_default=True,
    native_unit_of_measurement=UnitOfTime.MINUTES,
    state_class=SensorStateClass.TOTAL,
    name="Minutes Remaining",
)


PERCENTAGE_REMAINING_DESCRIPTION = SensorEntityDescription(
    key="percent_remain",
    translation_key="percent_remain",
    device_class=SensorDeviceClass.BATTERY,
    entity_registry_enabled_default=False,
    entity_registry_visible_default=True,
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.TOTAL,
    name="Percent Remaining",
)


SENSOR_DESCRIPTIONS = [
    WATTS_IMPORT_DESCRIPTION,
    WATTS_EXPORT_DESCRIPTION,
    MINUTES_REMAINING_DESCRIPTION,
    PERCENTAGE_REMAINING_DESCRIPTION,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform for Allpowers."""
    data: AllpowersBLEData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AllpowersBLESensor(
            data.coordinator,
            data.device,
            entry.title,
            description,
        )
        for description in SENSOR_DESCRIPTIONS
    )


class AllpowersBLESensor(CoordinatorEntity[AllpowersBLECoordinator], SensorEntity):
    """Generic sensor for Allpowers."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AllpowersBLECoordinator,
        device: AllpowersBLE,
        name: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._device = device
        self._key = description.key
        self.entity_description = description
        self._attr_unique_id = f"{device.address}_{self._key}"
        self._attr_device_info = DeviceInfo(
            name=name,
            connections={(dr.CONNECTION_BLUETOOTH, device.address)},
        )
        self._attr_native_value = getattr(self._device, self._key)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = getattr(self._device, self._key)
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Unavailable if coordinator isn't connected."""
        return self._coordinator.connected and super().available
