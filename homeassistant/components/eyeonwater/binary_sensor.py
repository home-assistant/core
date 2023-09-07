"""Support for EyeOnWater binary sensors."""
from dataclasses import dataclass

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
from pyonwater import Meter

from .const import DATA_COORDINATOR, DATA_SMART_METER, DOMAIN, WATER_METER_NAME


@dataclass
class Description:
    """Binary sensor description."""

    key: str
    device_class: BinarySensorDeviceClass
    translation_key: str | None = None


FLAG_SENSORS = [
    Description(
        key="leak",
        translation_key="leak",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    Description(
        key="empty_pipe",
        translation_key="emptypipe",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    Description(
        key="tamper",
        translation_key="tamper",
        device_class=BinarySensorDeviceClass.TAMPER,
    ),
    Description(
        key="cover_removed",
        translation_key="coverremoved",
        device_class=BinarySensorDeviceClass.TAMPER,
    ),
    Description(
        key="reverse_flow",
        translation_key="reverseflow",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    Description(
        key="low_battery",
        device_class=BinarySensorDeviceClass.BATTERY,
    ),
    Description(
        key="battery_charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the EyeOnWater sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    meters = hass.data[DOMAIN][config_entry.entry_id][DATA_SMART_METER].meters

    sensors = []
    for meter in meters:
        sensors += [
            (EyeOnWaterBinarySensor(meter, coordinator, description))
            for description in FLAG_SENSORS
        ]

    async_add_entities(sensors, update_before_add=False)


class EyeOnWaterBinarySensor(CoordinatorEntity, RestoreEntity, BinarySensorEntity):
    """Representation of an EyeOnWater binary flag sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        meter: Meter,
        coordinator: DataUpdateCoordinator,
        description: Description,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = BinarySensorEntityDescription(
            key=description.key,
            device_class=description.device_class,
            translation_key=description.translation_key,
        )
        self.meter = meter
        self._state = False
        self._available = False
        self._attr_unique_id = f"{description.key}_{self.meter.meter_uuid}"
        self._attr_is_on = self._state
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.meter.meter_uuid)},
            name=f"{WATER_METER_NAME} {self.meter.meter_id}",
            model=self.meter.meter_info.reading.model,
            manufacturer=self.meter.meter_info.reading.customer_name,
            hw_version=self.meter.meter_info.reading.hardware_version,
            sw_version=self.meter.meter_info.reading.firmware_version,
        )

    def get_flag(self) -> bool:
        """Get flag value."""
        return self.meter.meter_info.reading.flags.__dict__[self.entity_description.key]

    @callback
    def _state_update(self):
        """Call when the coordinator has an update."""
        self._available = self.coordinator.last_update_success
        if self._available:
            self._state = self.get_flag()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(self.coordinator.async_add_listener(self._state_update))

        if self.coordinator.last_update_success:
            return

        if last_state := await self.async_get_last_state():
            self._state = last_state.state
            self._available = True
