"""Outside temperature sensor for Fujitsu FGlair HVAC systems."""

from ayla_iot_unofficial.fujitsu_hvac import FujitsuHVAC

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FGLairConfigEntry, FGLairCoordinator
from .entity import FGLairEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FGLairConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one Fujitsu HVAC device."""
    async_add_entities(
        FGLairOutsideTemperature(entry.runtime_data, device)
        for device in entry.runtime_data.data.values()
        if device.outdoor_temperature is not None
    )


class FGLairOutsideTemperature(FGLairEntity, SensorEntity):
    """Entity representing outside temperature sensed by the outside unit of a Fujitsu Heatpump."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "fglair_outside_temp"

    def __init__(self, coordinator: FGLairCoordinator, device: FujitsuHVAC) -> None:
        """Store the representation of the device."""
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{device.device_serial_number}_outside_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the sensed outdoor temperature un celsius."""
        return self.device.outdoor_temperature  # type: ignore[no-any-return]
