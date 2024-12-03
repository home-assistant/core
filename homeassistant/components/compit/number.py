"""Code for the Compit number component."""

from typing import Any

from compit_inext_api import Device, Parameter

from homeassistant.components.number import NumberEntity
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
    """Set up the entry for the component."""
    coordinator: CompitDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_devices(
        [
            CompitNumber(coordinator, device, parameter, device_definition.name)
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
            == Platform.NUMBER
        ]
    )


class CompitNumber(CoordinatorEntity[CompitDataUpdateCoordinator], NumberEntity):
    """Represents a number entity for the Compit component."""

    def __init__(
        self,
        coordinator: CompitDataUpdateCoordinator,
        device: Device,
        parameter: Parameter,
        device_name: str,
    ) -> None:
        """Initialize the CompitNumber class."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.unique_id = f"number_{device.label}{parameter.parameter_code}"
        self.label = f"{device.label} {parameter.label}"
        self.parameter = parameter
        self.device = device
        self.device_name = device_name
        self.param = self.coordinator.data[self.device.id].state.get_parameter_value(
            self.parameter
        )
        if self.param is not None:
            self._value = float(self.param.value)
        else:
            self._value = float(0)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information about this number device."""
        return {
            "identifiers": {(DOMAIN, str(self.device.id))},
            "name": self.device.label,
            "manufacturer": MANURFACER_NAME,
            "model": self.device_name,
            "sw_version": "1.0",
        }

    @property
    def name(self) -> str:
        """Return the name of the number device."""
        return self.label

    @property
    def native_value(self) -> float:
        """Return the minimum value."""
        return self._value

    @property
    def native_min_value(self) -> float | int:
        """Return the minimum value of the number device."""
        if isinstance(self.parameter.min_value, (int, float)):
            return self.parameter.min_value
        if self.param is not None:
            return self.param.min or float(0)
        return float(0)

    @property
    def native_max_value(self) -> float | int:
        """Return the maximum value of the number device."""
        if isinstance(self.parameter.max_value, (int, float)):
            return self.parameter.max_value
        if self.param is not None:
            return self.param.max or float(0)
        return float(0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes for the number device."""
        items = []

        items.append(
            {
                "device": self.device.label,
                "device_id": self.device.id,
                "device_class": self.device.device_class,
                "device_type": self.device.type,
            }
        )

        return {
            "details": items,
        }

    async def async_set_native_value(self, value: float) -> None:
        """Set the native value of the number device."""

        if (
            await self.coordinator.api.update_device_parameter(
                self.device.id, self.parameter.parameter_code, value
            )
            is not False
        ):
            self._value = value
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
