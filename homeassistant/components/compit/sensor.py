"""Contains the CompitSensor class."""

from compit_inext_api import Device, Parameter

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANURFACER_NAME
from .coordinator import CompitDataUpdateCoordinator
from .sensor_matcher import SensorMatcher


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_devices: AddEntitiesCallback
) -> None:
    """Set up the entry."""
    coordinator: CompitDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_devices(
        [
            CompitSensor(coordinator, device, parameter, device_definition.name)
            for gate in coordinator.gates
            for device in gate.devices
            if (
                device_definition := next(
                    (
                        definition
                        for definition in coordinator.device_definitions.devices
                        if definition.code == device.type
                    ),
                    None,
                )
            )
            is not None
            for parameter in device_definition.parameters
            if SensorMatcher.get_platform(
                parameter,
                coordinator.data[device.id].state.get_parameter_value(parameter),
            )
            == Platform.SENSOR
        ]
    )


class CompitSensor(CoordinatorEntity[CompitDataUpdateCoordinator], SensorEntity):
    """Representation of a Compit sensor device."""

    def __init__(
        self,
        coordinator: CompitDataUpdateCoordinator,
        device: Device,
        parameter: Parameter,
        device_name: str,
    ) -> None:
        """Initialize the sensor device."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.unique_id = f"sensor_{device.label}{parameter.parameter_code}"
        self.label = f"{device.label} {parameter.label}"
        self.parameter = parameter
        self.device = device
        self.device_name = device_name

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information about this sensor device."""
        return {
            "identifiers": {(DOMAIN, str(self.device.id))},
            "name": self.device.label,
            "manufacturer": MANURFACER_NAME,
            "model": self.device_name,
            "sw_version": "1.0",
        }

    @property
    def name(self) -> str:
        """Return the name of the sensor device."""
        return f"{self.label}"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        value = self.coordinator.data[self.device.id].state.get_parameter_value(
            self.parameter
        )

        if value is None:
            return None
        if value.value_label is not None:
            return value.value_label
        if len(str(value.value)) > 100:
            return str(value.value)[:100] + "..."
        return value.value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of this sensor."""
        return self.parameter.unit
