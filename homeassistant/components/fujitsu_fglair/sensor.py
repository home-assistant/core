"""Outside temperature sensor for Fujitsu FGlair HVAC systems."""

from ayla_iot_unofficial.fujitsu_hvac import FujitsuHVAC

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .climate import FGLairConfigEntry
from .const import DOMAIN
from .coordinator import FGLairCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FGLairConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one Fujitsu HVAC device."""
    async_add_entities(
        FGLairOutsideTemperature(entry.runtime_data, device)
        for device in entry.runtime_data.data.values()
    )


class FGLairOutsideTemperature(CoordinatorEntity[FGLairCoordinator], SensorEntity):
    """Entity representing outside temperature sensed by the outside unit of a Fujitsu Heatpump."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True
    _attr_translation_key = "fglair_outside_temp"

    def __init__(self, coordinator: FGLairCoordinator, device: FujitsuHVAC) -> None:
        """Store the representation of the device."""
        super().__init__(coordinator, context=device.device_serial_number)

        self._attr_unique_id = device.device_serial_number
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_serial_number)},
            name=device.device_name,
            manufacturer="Fujitsu",
            model=device.property_values["model_name"],
            serial_number=device.device_serial_number,
            sw_version=device.property_values["mcu_firmware_version"],
        )

    @property
    def device(self) -> FujitsuHVAC:
        """Return the device object from the coordinator data."""
        return self.coordinator.data[self.coordinator_context]

    @property
    def native_value(self) -> float | None:
        """Return the sensed outdoor temperature un celsius."""
        return self.device.outdoor_temperature  # type: ignore[no-any-return]
