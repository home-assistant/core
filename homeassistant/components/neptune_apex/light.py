"""Support outlet status/control from Neptune Apex."""
import logging

import pynepsys

from homeassistant.components.light import ATTR_EFFECT, SUPPORT_EFFECT, Light

from . import NEPTUNE_APEX, NEPTUNE_APEX_COORDINATOR

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Parse through the Apex outlets and creates Outlet entities."""
    apex = hass.data[NEPTUNE_APEX]
    coordinator = hass.data[NEPTUNE_APEX_COORDINATOR]

    async_add_entities(
        Outlet(coordinator, apex, name) for name in coordinator.data.outlets
    )


class Outlet(Light):
    """Shoehorn the Apex outlet concept into a hass Light entity."""

    def __init__(self, coordinator, apex: pynepsys.Apex, name):
        """Initialize this outlet, storing reference to parent Apex."""
        self.coordinator = coordinator
        self._name = name
        self.apex = apex
        self.outlet: pynepsys.Outlet = apex.outlets[name]

    @property
    def name(self):
        """Name of this outlet (From the Apex), prefixed."""
        return f"apex.{self._name}"

    @property
    def unique_id(self):
        """Name of this outlet as defined in the Apex."""
        return f"{self.apex.serial}_{self.outlet.device_id}"

    @property
    def is_on(self):
        """Return True if the outlet is manually forced on or in AUTO mode and on."""
        return self.outlet.is_on()

    @property
    def supported_features(self):
        """We support effects as a hack to allow AUTO mode to exist."""
        return SUPPORT_EFFECT

    @property
    def effect(self):
        """Return the current state of the outlet.

        ON, OFF, AUTO are the useful effects for this integration, but you can
        read profile names for pumps and lights via this property as well.
        """
        return self.outlet.state

    @property
    def effect_list(self):
        """Return the profiles you can actually put this outlet into.

        AUTO represents automatic mode, ON/OFF being manually forced on/off
        ignoring outlet programming.
        """
        return ["AUTO", "ON", "OFF"]

    async def async_turn_on(self, **kwargs):
        """Turn the outlet on except if an effect is defined.

        If effect is AUTO, ON, or OFF, put the outlet into that mode.
        """
        if kwargs.get(ATTR_EFFECT) == "AUTO":
            _LOGGER.debug("Enabling AUTO for outlet %s", self.name)
            self.outlet.enable_auto()
            await self.apex.update_outlet(self.outlet)
            self.async_schedule_update_ha_state(True)
            _LOGGER.debug("Just turned on AUTO. is_on = %s", self.outlet.is_on())
        elif kwargs.get(ATTR_EFFECT) == "ON":
            await self.async_turn_on()
        elif kwargs.get(ATTR_EFFECT) == "OFF":
            await self.async_turn_off()
        else:
            _LOGGER.debug("Turning outlet ON for %s", self.name)
            self.outlet.force_on()
            await self.apex.update_outlet(self.outlet)
            self.async_schedule_update_ha_state()
            _LOGGER.debug("Just turned on outlet. is_on = %s", self.outlet.is_on())

    async def async_turn_off(self, **kwargs):
        """Turn the outlet off by forcing off, disabling AUTO if enabled."""
        self.outlet.force_off()
        await self.apex.update_outlet(self.outlet)
        self.async_schedule_update_ha_state()
        _LOGGER.debug("Just turned off outlet. is_on = %s", self.outlet.is_on())

    @property
    def icon(self):
        """We have a custom icon of a power socket."""
        return "mdi:power-socket-us"

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()
