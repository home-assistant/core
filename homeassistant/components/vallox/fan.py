"""Support for the Vallox ventilation unit fan."""

import logging

from homeassistant.components.fan import FanEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    DOMAIN,
    METRIC_KEY_MODE,
    METRIC_KEY_PROFILE_FAN_SPEED_AWAY,
    METRIC_KEY_PROFILE_FAN_SPEED_BOOST,
    METRIC_KEY_PROFILE_FAN_SPEED_HOME,
    MODE_OFF,
    MODE_ON,
    SIGNAL_VALLOX_STATE_UPDATE,
)

_LOGGER = logging.getLogger(__name__)

# Device attributes
ATTR_PROFILE_FAN_SPEED_HOME = {
    "description": "fan_speed_home",
    "metric_key": METRIC_KEY_PROFILE_FAN_SPEED_HOME,
}
ATTR_PROFILE_FAN_SPEED_AWAY = {
    "description": "fan_speed_away",
    "metric_key": METRIC_KEY_PROFILE_FAN_SPEED_AWAY,
}
ATTR_PROFILE_FAN_SPEED_BOOST = {
    "description": "fan_speed_boost",
    "metric_key": METRIC_KEY_PROFILE_FAN_SPEED_BOOST,
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the fan device."""
    if discovery_info is None:
        return

    client = hass.data[DOMAIN]["client"]

    client.set_settable_address(METRIC_KEY_MODE, int)

    device = ValloxFan(
        hass.data[DOMAIN]["name"], client, hass.data[DOMAIN]["state_proxy"]
    )

    async_add_entities([device], update_before_add=False)


class ValloxFan(FanEntity):
    """Representation of the fan."""

    def __init__(self, name, client, state_proxy):
        """Initialize the fan."""
        self._name = name
        self._client = client
        self._state_proxy = state_proxy
        self._available = False
        self._state = None
        self._fan_speed_home = None
        self._fan_speed_away = None
        self._fan_speed_boost = None

    @property
    def should_poll(self):
        """Do not poll the device."""
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def available(self):
        """Return if state is known."""
        return self._available

    @property
    def is_on(self):
        """Return if device is on."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return {
            ATTR_PROFILE_FAN_SPEED_HOME["description"]: self._fan_speed_home,
            ATTR_PROFILE_FAN_SPEED_AWAY["description"]: self._fan_speed_away,
            ATTR_PROFILE_FAN_SPEED_BOOST["description"]: self._fan_speed_boost,
        }

    async def async_added_to_hass(self):
        """Call to update."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_VALLOX_STATE_UPDATE, self._update_callback
            )
        )

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    async def async_update(self):
        """Fetch state from the device."""
        try:
            # Fetch if the whole device is in regular operation state.
            self._state = self._state_proxy.fetch_metric(METRIC_KEY_MODE) == MODE_ON

            # Fetch the profile fan speeds.
            self._fan_speed_home = int(
                self._state_proxy.fetch_metric(
                    ATTR_PROFILE_FAN_SPEED_HOME["metric_key"]
                )
            )
            self._fan_speed_away = int(
                self._state_proxy.fetch_metric(
                    ATTR_PROFILE_FAN_SPEED_AWAY["metric_key"]
                )
            )
            self._fan_speed_boost = int(
                self._state_proxy.fetch_metric(
                    ATTR_PROFILE_FAN_SPEED_BOOST["metric_key"]
                )
            )

        except (OSError, KeyError) as err:
            self._available = False
            _LOGGER.error("Error updating fan: %s", err)
            return

        self._available = True

    #
    # The fan entity model has changed to use percentages and preset_modes
    # instead of speeds.
    #
    # Please review
    # https://developers.home-assistant.io/docs/core/entity/fan/
    #
    async def async_turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        """Turn the device on."""
        _LOGGER.debug("Turn on: %s", speed)

        # Only the case speed == None equals the GUI toggle switch being
        # activated.
        if speed is not None:
            return

        if self._state is True:
            _LOGGER.error("Already on")
            return

        try:
            await self._client.set_values({METRIC_KEY_MODE: MODE_ON})

        except OSError as err:
            self._available = False
            _LOGGER.error("Error turning on: %s", err)
            return

        # This state change affects other entities like sensors. Force an immediate update that can
        # be observed by all parties involved.
        await self._state_proxy.async_update(None)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the device off."""
        if self._state is False:
            _LOGGER.error("Already off")
            return

        try:
            await self._client.set_values({METRIC_KEY_MODE: MODE_OFF})

        except OSError as err:
            self._available = False
            _LOGGER.error("Error turning off: %s", err)
            return

        # Same as for turn_on method.
        await self._state_proxy.async_update(None)
