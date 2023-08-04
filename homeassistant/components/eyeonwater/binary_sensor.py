"""Support for EyeOnWater binary sensors."""
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    DATA_COORDINATOR,
    DATA_SMART_METER,
    DOMAIN,
)
from .eow import Meter

FLAG_SENSORS = [
    BinarySensorEntityDescription(
        key="Leak",
        name="Leak Sensor",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    BinarySensorEntityDescription(
        key="EmptyPipe",
        name="Empty Pipe",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="Tamper",
        name="Tamper",
        device_class=BinarySensorDeviceClass.TAMPER,
    ),
    BinarySensorEntityDescription(
        key="CoverRemoved",
        name="Cover Removed",
        device_class=BinarySensorDeviceClass.TAMPER,
    ),
    BinarySensorEntityDescription(
        key="ReverseFlow",
        name="Reverse Waterflow",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="LowBattery",
        name="Low Battery",
        device_class=BinarySensorDeviceClass.BATTERY,
    ),
    BinarySensorEntityDescription(
        key="BatteryCharging",
        name="Battery Charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the EyeOnWater sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    meters = hass.data[DOMAIN][config_entry.entry_id][DATA_SMART_METER].meters

    sensors = []
    for meter in meters:
        for description in FLAG_SENSORS:
            sensors.append(EyeOnWaterBinarySensor(meter, coordinator, description))

    async_add_entities(sensors, False)


class EyeOnWaterBinarySensor(CoordinatorEntity, RestoreEntity, BinarySensorEntity):
    """Representation of an EyeOnWater binary flag sensor."""

    def __init__(
        self,
        meter: Meter,
        coordinator: DataUpdateCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.meter = meter
        self._state = False
        self._available = False
        self._attr_unique_id = f"{description.key}_{self.meter.meter_uuid}"
        self._attr_is_on = self._state
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, meter.meter_uuid)},
            name=f"Water Meter {meter.meter_info['meter_id']}",
        )

    @callback
    def _state_update(self):
        """Call when the coordinator has an update."""
        self._available = self.coordinator.last_update_success
        if self._available:
            self._state = self.meter.get_flags(self.entity_description.key)
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(self.coordinator.async_add_listener(self._state_update))

        if self.coordinator.last_update_success:
            return

        if last_state := await self.async_get_last_state():
            self._state = last_state.state
            self._available = True
