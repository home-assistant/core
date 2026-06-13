"""Support for Aqualink temperature sensors."""

from iaqualink.device import AqualinkBinarySensor, AqualinkDevice, AqualinkSensor

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AqualinkConfigEntry
from .coordinator import AqualinkDataUpdateCoordinator
from .entity import AqualinkEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AqualinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up discovered sensors."""
    for coordinator in config_entry.runtime_data.coordinators.values():

        def _async_add_new_devices(
            devices: list[AqualinkDevice],
            _coordinator: AqualinkDataUpdateCoordinator = coordinator,
        ) -> None:
            async_add_entities(
                HassAqualinkSensor(_coordinator, dev)
                for dev in devices
                if isinstance(dev, AqualinkSensor)
                and not isinstance(dev, AqualinkBinarySensor)
            )

        coordinator.new_device_callbacks.append(_async_add_new_devices)
        _async_add_new_devices(list(coordinator.data.values()))


class HassAqualinkSensor(AqualinkEntity[AqualinkSensor], SensorEntity):
    """Representation of a sensor."""

    def __init__(
        self, coordinator: AqualinkDataUpdateCoordinator, dev: AqualinkSensor
    ) -> None:
        """Initialize AquaLink sensor."""
        super().__init__(coordinator, dev)
        if not dev.name.endswith("_temp"):
            return
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        if dev.system.temp_unit == "F":
            self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
            return
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the sensor."""
        if self.dev.state == "":
            return None

        try:
            return int(self.dev.state)
        except ValueError:
            return float(self.dev.state)
