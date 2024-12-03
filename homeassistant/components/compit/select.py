"""Contains the select component for the Compit integration."""

from typing import Any

from compit_inext_api import Device, Parameter

from homeassistant.components.select import SelectEntity
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
    """Set up the Compit integration entry."""
    coordinator: CompitDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_devices(
        [
            CompitSelect(coordinator, device, parameter, device_definition.name)
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
            == Platform.SELECT
        ]
    )


class CompitSelect(CoordinatorEntity[CompitDataUpdateCoordinator], SelectEntity):
    """Represents a select entity for the Compit integration."""

    def __init__(
        self,
        coordinator: CompitDataUpdateCoordinator,
        device: Device,
        parameter: Parameter,
        device_name: str,
    ) -> None:
        """Initialize the CompitSelect class."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.unique_id = f"select_{device.label}{parameter.parameter_code}"
        self.label = f"{device.label} {parameter.label}"
        self.parameter = parameter
        self.device = device
        self.device_name = device_name
        value = self.coordinator.data[self.device.id].state.get_parameter_value(
            self.parameter
        )
        if self.parameter.details is not None:
            self._value = next(
                detail
                for detail in self.parameter.details
                if detail is not None
                and value is not None
                and detail.state == value.value
            )
            self._attr_current_option = self._value.description

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the device information for the CompitSelect entity."""
        return {
            "identifiers": {(DOMAIN, str(self.device.id))},
            "name": self.device.label,
            "manufacturer": MANURFACER_NAME,
            "model": self.device_name,
            "sw_version": "1.0",
        }

    @property
    def name(self) -> str:
        """Return the name of the CompitSelect entity."""
        return f"{self.label}"

    @property
    def options(self) -> list[str]:
        """Return the list of options for the select entity."""
        if self.parameter.details is None:
            return []
        return [
            detail.description
            for detail in self.parameter.details
            if detail is not None and detail.param is not None
        ]

    @property
    def native_value(self) -> str | None:
        """Return the state of the CompitSelect entity."""
        if self.parameter.details is None:
            return None
        if self._value is not None:
            parameter = next(
                (
                    detail
                    for detail in self.parameter.details
                    if detail is not None and detail.param == self._value.param
                ),
                None,
            )
            if parameter is not None:
                return parameter.description
            return self._value.description

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the extra state attributes for the CompitSelect entity."""
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

    async def async_select_option(self, option: str) -> None:
        """Select an option for the CompitSelect entity."""
        if self.parameter.details is None:
            return
        value = next(
            (
                detail
                for detail in self.parameter.details
                if detail is not None and detail.description == option
            ),
            None,
        )
        if value is None:
            return
        self._value = value
        self._attr_current_option = value.description
        result = await self.coordinator.api.update_device_parameter(
            self.device.id, self.parameter.parameter_code, value.state
        )
        if result:
            self._attr_current_option = value.description
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
