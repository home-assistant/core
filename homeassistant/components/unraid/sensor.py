"""Support for Unraid sensors."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import COORD_DATA_KEY
from .coordinator import UnraidConfigEntry, UnraidUpdateCoordinator
from .entity import UnraidEntity
from .models import ArrayDisk, UnraidData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Unraid sensors based on a config entry."""

    coordinator = entry.runtime_data

    data: UnraidData = coordinator.data[COORD_DATA_KEY]
    disks = data.array.disks
    sensors: list[DriveTemperatureSensor] = [
        DriveTemperatureSensor(coordinator, disk) for disk in disks
    ]

    async_add_entities(sensors)


class DriveTemperatureSensor(UnraidEntity, SensorEntity):
    """Defines a sensor."""

    _data: ArrayDisk

    def __init__(
        self, coordinator: UnraidUpdateCoordinator, drive_data: ArrayDisk
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._data = drive_data
        self._attr_name = f"Temperature {drive_data.name}"
        self._attr_unique_id += f"{drive_data.name}_temperature"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_state_class = "measurement"
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> int:
        """Return the state of the entity."""
        return self._data.temp
