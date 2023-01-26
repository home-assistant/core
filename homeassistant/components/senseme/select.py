"""Support for Big Ass Fans SenseME selects."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aiosenseme import SensemeFan
from aiosenseme.device import SensemeDevice

from homeassistant import config_entries
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SensemeEntity

SMART_MODE_TO_HASS = {
    "OFF": "Off",
    "COOLING": "Cooling",
    "HEATING": "Heating",
    "FOLLOWTSTAT": "Follow Thermostat",
}
HASS_TO_SMART_MODE = {v: k for k, v in SMART_MODE_TO_HASS.items()}


@dataclass
class SenseMESelectEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[SensemeFan], str]
    set_fn: Callable[[SensemeFan, str], None]


@dataclass
class SenseMESelectEntityDescription(
    SelectEntityDescription, SenseMESelectEntityDescriptionMixin
):
    """Describes SenseME select entity."""


def _set_smart_mode(device: SensemeDevice, value: str) -> None:
    device.fan_smartmode = HASS_TO_SMART_MODE[value]


FAN_SELECTS = [
    SenseMESelectEntityDescription(
        key="smart_mode",
        name="Smart Mode",
        value_fn=lambda device: SMART_MODE_TO_HASS[device.fan_smartmode],
        set_fn=_set_smart_mode,
        options=list(SMART_MODE_TO_HASS.values()),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SenseME fan selects."""
    device = hass.data[DOMAIN][entry.entry_id]
    if device.is_fan:
        async_add_entities(
            HASensemeSelect(device, description) for description in FAN_SELECTS
        )


class HASensemeSelect(SensemeEntity, SelectEntity):
    """SenseME select component."""

    entity_description: SenseMESelectEntityDescription

    def __init__(
        self, device: SensemeFan, description: SenseMESelectEntityDescription
    ) -> None:
        """Initialize the entity."""
        self.entity_description = description
        super().__init__(device, f"{device.name} {description.name}")
        self._attr_unique_id = f"{self._device.uuid}-{description.key}"

    @property
    def current_option(self) -> str:
        """Return the current value."""
        return self.entity_description.value_fn(self._device)

    async def async_select_option(self, option: str) -> None:
        """Set the option."""
        self.entity_description.set_fn(self._device, option)
