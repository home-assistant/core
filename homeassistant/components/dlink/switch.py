"""Support for D-Link Power Plug Switches."""

from __future__ import annotations

import logging
from typing import Any, Optional, cast

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_TOTAL_CONSUMPTION, DOMAIN
from .coordinator import DlinkCoordinator
from .entity import DLinkEntity

SWITCH_TYPE = SwitchEntityDescription(
    key="switch",
)


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the D-Link Power Plug sensors."""
    coordinator: DlinkCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [SmartPlugSwitch(coordinator, entry, SWITCH_TYPE)]
    async_add_entities(entities)


class SmartPlugSwitch(DLinkEntity, SwitchEntity):
    """Representation of a D-Link Smart Plug switch."""

    _attr_name = None

    # Deprecated, can be removed in 2024.11
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the device."""
        try:
            _temperature: Optional[int] = self.coordinator.data.get("temperature")
            if _temperature is not None:
                temperature = self.hass.config.units.temperature(
                    int(_temperature), UnitOfTemperature.CELSIUS
                )
        except ValueError:
            temperature = None

        try:
            _total_consumption: Optional[float] = self.coordinator.data.get(
                "total_consumption"
            )
            if _total_consumption is not None:
                total_consumption = float(_total_consumption)
        except ValueError:
            total_consumption = None

        return {
            ATTR_TOTAL_CONSUMPTION: total_consumption,
            ATTR_TEMPERATURE: temperature,
        }

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.coordinator.data.get("state") == "ON"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""

        def _turn_on(smartplug) -> None:
            smartplug.state = "ON"

        await self.hass.async_add_executor_job(_turn_on, self.coordinator.smartplug)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""

        def _turn_off(smartplug) -> None:
            smartplug.state = "OFF"

        await self.hass.async_add_executor_job(_turn_off, self.coordinator.smartplug)
        await self.coordinator.async_request_refresh()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return cast(bool, self.coordinator.data.get("available"))
