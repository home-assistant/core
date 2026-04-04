"""Support for Guntamatic sensors in Home Assistant."""

from datetime import timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

UPDATE_INTERVAL = timedelta(seconds=60)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Guntamatic sensors from config entry."""

    data = entry.runtime_data
    coordinator = data.coordinator
    heater = data.heater

    # Create one entity per sensor
    sensors = [
        GuntamaticSensor(coordinator, name, heater.host) for name in coordinator.data
    ]

    async_add_entities(sensors)


class GuntamaticSensor(CoordinatorEntity, SensorEntity):
    """Representation of a single Guntamatic sensor."""

    def __init__(self, coordinator, name, host):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._name = name
        self._attr_has_entity_name = True
        self._attr_name = name
        # serial might not be set on all devices
        serial = coordinator.data.get("Serial", [None])[0] or host

        self._attr_unique_id = (
            f"guntamatic_{serial.replace('.', '_')}_{name.replace(' ', '_')}"
        )

        unit = coordinator.data[name][1]
        self._attr_native_unit_of_measurement = unit
        # if no unit is given by the guntamatic, it's a string, so set None
        if not unit:
            self._attr_native_unit_of_measurement = None
            self._attr_state_class = None
            self._attr_device_class = SensorDeviceClass.ENUM

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name="Guntamatic Heater",
            manufacturer="Guntamatic",
            serial_number=serial if serial != host else None,
            sw_version=coordinator.data.get("Version", [None])[0],
        )

    @property
    def native_value(self):
        """Return the current value of the sensor."""
        return self.coordinator.data[self._attr_name][0]

    @property
    def native_unit_of_measurement(self):
        """Return the current unit of the sensor."""
        return self.coordinator.data[self._attr_name][1]
