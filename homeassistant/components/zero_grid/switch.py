"""Switch entities for ZeroGrid."""

from __future__ import annotations

import logging
import sys
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ZeroGrid switch platform."""
    _LOGGER.debug("Setting up ZeroGrid switch platform")

    enable_switch = EnableLoadControlSwitch()
    allow_grid_import_switch = AllowGridImportSwitch()

    # Store references in hass.data for updates
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["enable_load_control_switch"] = enable_switch
    hass.data[DOMAIN]["allow_grid_import_switch"] = allow_grid_import_switch

    async_add_entities([enable_switch, allow_grid_import_switch])


class EnableLoadControlSwitch(SwitchEntity):
    """Switch to enable/disable load control."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_is_on: bool

    def __init__(self) -> None:
        """Initialize the switch."""
        self._attr_name = "Enable load control"
        self._attr_unique_id = f"{DOMAIN}_enable_load_control"
        self._attr_is_on = True

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return bool(self._attr_is_on)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._attr_is_on = True
        self.async_write_ha_state()
        _LOGGER.info("Load control enabled")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._attr_is_on = False
        self.async_write_ha_state()
        _LOGGER.info("Load control disabled")

    @callback
    def update_state(self, is_on: bool) -> None:
        """Update the switch state."""
        self._attr_is_on = is_on
        self.async_write_ha_state()


class AllowGridImportSwitch(SwitchEntity):
    """Switch to allow/disallow grid import for load control."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_is_on: bool

    def __init__(self) -> None:
        """Initialize the switch."""
        self._attr_name = "Allow grid import"
        self._attr_unique_id = f"{DOMAIN}_allow_grid_import"
        self._attr_is_on = True

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to hass."""
        await super().async_added_to_hass()
        # Sync initial state to the integration
        await self._update_integration_state()

    @property
    def is_on(self) -> bool:
        """Return true if grid import is allowed."""
        return bool(self._attr_is_on)

    async def _update_integration_state(self) -> None:
        """Update the integration's STATE and trigger recalculation."""
        # Import here to avoid circular import
        if hasattr(self.hass, "data") and DOMAIN in self.hass.data:
            # Get the STATE from the main module
            if "homeassistant.components.zero_grid" in sys.modules:
                zero_grid_module = sys.modules["homeassistant.components.zero_grid"]
                if hasattr(zero_grid_module, "STATE"):
                    zero_grid_module.STATE.allow_grid_import = self._attr_is_on
                    # Trigger recalculation
                    if hasattr(zero_grid_module, "recalculate_load_control"):
                        await zero_grid_module.recalculate_load_control(self.hass)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Allow grid import."""
        self._attr_is_on = True
        self.async_write_ha_state()
        _LOGGER.info("Grid import allowed")
        await self._update_integration_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disallow grid import."""
        self._attr_is_on = False
        self.async_write_ha_state()
        _LOGGER.info("Grid import disallowed")
        await self._update_integration_state()

    @callback
    def update_state(self, is_on: bool) -> None:
        """Update the switch state."""
        self._attr_is_on = is_on
        self.async_write_ha_state()
