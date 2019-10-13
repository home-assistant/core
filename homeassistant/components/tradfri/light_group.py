"""Support for IKEA Tradfri light groups."""
import logging

from pytradfri.error import PytradfriError

from homeassistant.components.light import Light, ATTR_TRANSITION, ATTR_BRIGHTNESS
from homeassistant.core import callback
from .const import SUPPORTED_GROUP_FEATURES

_LOGGER = logging.getLogger(__name__)


class TradfriLightGroup(Light):
    """The platform class required by hass."""

    def __init__(self, group, api, gateway_id):
        """Initialize a Group."""
        self._api = api
        self._unique_id = f"group-{gateway_id}-{group.id}"
        self._group = group
        self._name = group.name

        self._refresh(group)

    async def async_added_to_hass(self):
        """Start thread when added to hass."""
        self._async_start_observe()

    @property
    def unique_id(self):
        """Return unique ID for this group."""
        return self._unique_id

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_GROUP_FEATURES

    @property
    def name(self):
        """Return the display name of this group."""
        return self._name

    @property
    def is_on(self):
        """Return true if group lights are on."""
        return self._group.state

    @property
    def brightness(self):
        """Return the brightness of the group lights."""
        return self._group.dimmer

    async def async_turn_off(self, **kwargs):
        """Instruct the group lights to turn off."""
        await self._api(self._group.set_state(0))

    async def async_turn_on(self, **kwargs):
        """Instruct the group lights to turn on, or dim."""
        keys = {}
        if ATTR_TRANSITION in kwargs:
            keys["transition_time"] = int(kwargs[ATTR_TRANSITION]) * 10

        if ATTR_BRIGHTNESS in kwargs:
            if kwargs[ATTR_BRIGHTNESS] == 255:
                kwargs[ATTR_BRIGHTNESS] = 254

            await self._api(self._group.set_dimmer(kwargs[ATTR_BRIGHTNESS], **keys))
        else:
            await self._api(self._group.set_state(1))

    @callback
    def _async_start_observe(self, exc=None):
        """Start observation of light."""
        if exc:
            _LOGGER.warning("Observation failed for %s", self._name, exc_info=exc)

        try:
            cmd = self._group.observe(
                callback=self._observe_update,
                err_callback=self._async_start_observe,
                duration=0,
            )
            self.hass.async_create_task(self._api(cmd))
        except PytradfriError as err:
            _LOGGER.warning("Observation failed, trying again", exc_info=err)
            self._async_start_observe()

    def _refresh(self, group):
        """Refresh the light data."""
        self._group = group
        self._name = group.name

    @callback
    def _observe_update(self, tradfri_device):
        """Receive new state data for this light."""
        self._refresh(tradfri_device)
        self.async_schedule_update_ha_state()

    async def async_update(self):
        """Fetch new state data for the group."""
        await self._api(self._group.update())
