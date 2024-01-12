"""Support for switches through the SmartThings cloud API."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pysmartthings import Capability

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SmartThingsEntity
from .const import DATA_BROKERS, DOMAIN
from .utils import format_component_name, get_device_attributes, get_device_status


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add switches for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]

    entities = []

    for device in broker.devices.values():
        has_switch = broker.any_assigned(device.device_id, Platform.SWITCH)

        if not has_switch:
            continue

        device_components = get_device_attributes(device)

        for component_id in list(device_components.keys()):
            attributes = device_components[component_id]

            if attributes is None or Platform.SWITCH in attributes:
                entities.append(SmartThingsSwitch(device, component_id))

    async_add_entities(entities)


def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
    """Return all capabilities supported if minimum required are present."""
    # Must be able to be turned on/off.
    if Capability.switch in capabilities:
        return [Capability.switch, Capability.energy_meter, Capability.power_meter]
    return None


class SmartThingsSwitch(SmartThingsEntity, SwitchEntity):
    """Define a SmartThings switch."""

    def __init__(self, device, component_id: str | None = None) -> None:
        """Init the class."""
        super().__init__(device)
        self._component_id = component_id
        self._external_component_id = "main" if component_id is None else component_id

        self._attr_name = format_component_name(
            device.label, Platform.SWITCH, component_id
        )
        self._attr_unique_id = format_component_name(
            device.device_id, Platform.SWITCH, component_id, "."
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._device.switch_off(
            set_status=True, component_id=self._external_component_id
        )
        # State is set optimistically in the command above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._device.switch_on(
            set_status=True, component_id=self._external_component_id
        )
        # State is set optimistically in the command above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        status = get_device_status(self._device, self._component_id)

        return status.switch
