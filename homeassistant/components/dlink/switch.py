"""Support for D-Link Power Plug Switches."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_TOTAL_CONSUMPTION, DOMAIN
from .entity import DLinkEntity

SCAN_INTERVAL = timedelta(minutes=2)

SWITCH_TYPE = SwitchEntityDescription(
    key="switch",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the D-Link Power Plug switch."""
    async_add_entities(
        [SmartPlugSwitch(entry, hass.data[DOMAIN][entry.entry_id], SWITCH_TYPE)],
        True,
    )


class SmartPlugSwitch(DLinkEntity, SwitchEntity):
    """Representation of a D-Link Smart Plug switch."""

    _attr_name = None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the device."""
        try:
            temperature = self.hass.config.units.temperature(
                int(self.data.temperature), UnitOfTemperature.CELSIUS
            )
        except ValueError:
            temperature = None

        try:
            total_consumption = float(self.data.total_consumption)
        except ValueError:
            total_consumption = None

        return {
            ATTR_TOTAL_CONSUMPTION: total_consumption,
            ATTR_TEMPERATURE: temperature,
        }

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.data.state == "ON"

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.data.smartplug.state = "ON"

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.data.smartplug.state = "OFF"

    def update(self) -> None:
        """Get the latest data from the smart plug and updates the states."""
        self.data.update()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.data.available
