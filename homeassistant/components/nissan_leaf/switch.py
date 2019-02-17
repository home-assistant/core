"""Charge and Climate Control Support for the Nissan Leaf."""
import logging

from homeassistant.components.nissan_leaf import (
    DATA_CHARGING, DATA_CLIMATE, DATA_LEAF, LeafEntity)
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['nissan_leaf']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Nissan Leaf switch platform setup."""
    devices = []
    for value in hass.data[DATA_LEAF].values():
        devices.append(LeafChargeSwitch(value))
        devices.append(LeafClimateSwitch(value))

    add_devices(devices, True)


class LeafClimateSwitch(LeafEntity, ToggleEntity):
    """Nissan Leaf Climate Control switch."""

    @property
    def name(self):
        """Switch name."""
        return "{} {}".format(self.car.leaf.nickname, "Climate Control")

    def log_registration(self):
        """Log registration."""
        _LOGGER.debug(
            "Registered LeafClimateSwitch component with HASS for VIN %s",
            self.car.leaf.vin)

    @property
    def device_state_attributes(self):
        """Return climate control attributes."""
        attrs = super().device_state_attributes
        attrs["updated_on"] = self.car.last_climate_response
        return attrs

    @property
    def is_on(self):
        """Return true if climate control is on."""
        return self.car.data[DATA_CLIMATE]

    async def async_turn_on(self, **kwargs):
        """Turn on climate control."""
        if await self.car.async_set_climate(True):
            self.car.data[DATA_CLIMATE] = True

    async def async_turn_off(self, **kwargs):
        """Turn off climate control."""
        if await self.car.async_set_climate(False):
            self.car.data[DATA_CLIMATE] = False

    # @MartinHjelmare would like removed - think provides nice UI feedback
    # for switch.
    # Think VolvoOnCall component hase different icons for the switches.
    @property
    def icon(self):
        """Climate control icon."""
        if self.car.data[DATA_CLIMATE]:
            return 'mdi:fan'
        return 'mdi:fan-off'


class LeafChargeSwitch(LeafEntity, ToggleEntity):
    """Nissan Leaf Charging On switch."""

    @property
    def name(self):
        """Switch name."""
        return "{} {}".format(self.car.leaf.nickname, "Charging Status")

    # @MartinHjelmare would like removed - think provides nice UI feedback
    # for switch
    # Think VolvoOnCall component hase different icons for the switches.
    @property
    def icon(self):
        """Charging switch icon."""
        if self.car.data[DATA_CHARGING]:
            return 'mdi:flash'
        return 'mdi:flash-off'

    @property
    def is_on(self):
        """Return true if charging."""
        return self.car.data[DATA_CHARGING]

    async def async_turn_on(self, **kwargs):
        """Start car charging."""
        if await self.car.async_start_charging():
            self.car.data[DATA_CHARGING] = True

    # @MartinHjelmare says should be removed if we don't support it.
    #                 Maybe it should be a scene?
    # Unsure if better to provide as a sensor for the state, and a service to
    # start a charge, e.g.
    # - service: nissan_leaf.start_charging
    #   data:
    #     vin: XXXXXXXXXX
    def turn_off(self, **kwargs):
        """Nissan API doesn't allow stopping of charge remotely."""
        _LOGGER.info(
            "Cannot turn off Leaf charging."
            " Nissan API does not support stopping charge remotely")
