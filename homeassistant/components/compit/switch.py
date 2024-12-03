"""CompitSwitch class for controlling switch entities."""

from typing import Any

from compit_inext_api import Device, Parameter

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CompitDataUpdateCoordinator
from .sensor_matcher import SensorMatcher


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_devices: AddEntitiesCallback
) -> None:
    """Set up the CompitSwitch platform from a config entry."""
    coordinator: CompitDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_devices(
        [
            CompitSwitch(coordinator, device, parameter, device_definition.name)
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
            == Platform.SWITCH
        ]
    )


class CompitSwitch(CoordinatorEntity[CompitDataUpdateCoordinator], SwitchEntity):
    """Representation of a Compit switch device."""

    def __init__(
        self,
        coordinator: CompitDataUpdateCoordinator,
        device: Device,
        parameter: Parameter,
        device_name: str,
    ) -> None:
        """Initialize the switch device."""
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
        self._value = 0
        if value is not None and self.parameter.details is not None:
            par = next(
                (
                    detail
                    for detail in self.parameter.details
                    if detail is not None and detail.param == value.value_code
                ),
                None,
            )
            if par is not None:
                self._value = par.state

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information about this switch device."""
        return {
            "identifiers": {(DOMAIN, str(self.device.id))},
            "name": self.device.label,
            "manufacturer": "Compit",
            "model": self.device_name,
            "sw_version": "1.0",
        }

    @property
    def name(self) -> str:
        """Return the name of the switch device."""
        return f"{self.label}"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._value == 1

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes for the switch device."""
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch asynchronously."""
        if (
            await self.coordinator.api.update_device_parameter(
                self.device.id, self.parameter.parameter_code, 1
            )
            is not False
        ):
            await self.coordinator.async_request_refresh()
        self._value = 1
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch asynchronously."""

        if (
            await self.coordinator.api.update_device_parameter(
                self.device.id, self.parameter.parameter_code, 0
            )
            is not False
        ):
            await self.coordinator.async_request_refresh()
        self._value = 0
        self.async_write_ha_state()

    async def async_toggle(self, **kwargs: Any) -> None:
        """Change state of the switch asynchronously."""
        if self.is_on:
            await self.async_turn_off()
        else:
            await self.async_turn_on()
