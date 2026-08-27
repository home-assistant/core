"""Support for Sofar switches."""

from dataclasses import dataclass
from typing import Any, override

from modbus_connection import ModbusError
from sofar_modbus.modern.enums import RemoteSwitchOnOff

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import SofarConfigEntry
from .entity import SofarEntity, SofarEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SofarSwitchEntityDescription(SwitchEntityDescription, SofarEntityDescription):
    """Describe a Sofar switch entity."""


SWITCH_DESCRIPTIONS: tuple[SofarSwitchEntityDescription, ...] = (
    SofarSwitchEntityDescription(
        key="remote_switch_on_off",
        component="remote",
        translation_key="remote_switch_on_off",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SofarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sofar Inverter Modbus switch platform."""
    runtime_data = entry.runtime_data
    served = runtime_data.served_components
    async_add_entities(
        SofarSwitch(runtime_data, description)
        for description in SWITCH_DESCRIPTIONS
        if description.component in served
    )


class SofarSwitch(SofarEntity, SwitchEntity):
    """Defines a Sofar switch entity."""

    entity_description: SofarSwitchEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the remote switch is on."""
        component = getattr(self.coordinator.device, self.entity_description.component)
        value = getattr(component, self.entity_description.key)
        return None if value is None else bool(value)

    async def _async_write(self, value: RemoteSwitchOnOff) -> None:
        """Write the switch state to the device."""
        component = getattr(self.coordinator.device, self.entity_description.component)
        try:
            await component.write(self.entity_description.key, value)
        except ModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the remote switch on."""
        await self._async_write(RemoteSwitchOnOff.ON)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the remote switch off."""
        await self._async_write(RemoteSwitchOnOff.OFF)
