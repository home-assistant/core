"""Support for IKEA Tradfri covers."""
import logging

from pytradfri.error import PytradfriError

from homeassistant.components.cover import (
    CoverDevice,
    ATTR_POSITION,
    SUPPORT_OPEN,
    SUPPORT_CLOSE,
    SUPPORT_SET_POSITION,
)
from homeassistant.core import callback
from .const import DOMAIN, KEY_GATEWAY, KEY_API, CONF_GATEWAY_ID

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Load Tradfri covers based on a config entry."""
    gateway_id = config_entry.data[CONF_GATEWAY_ID]
    api = hass.data[KEY_API][config_entry.entry_id]
    gateway = hass.data[KEY_GATEWAY][config_entry.entry_id]

    devices_commands = await api(gateway.get_devices())
    devices = await api(devices_commands)
    covers = [dev for dev in devices if dev.has_blind_control]
    if covers:
        async_add_entities(TradfriCover(cover, api, gateway_id) for cover in covers)


class TradfriCover(CoverDevice):
    """The platform class required by Home Assistant."""

    def __init__(self, cover, api, gateway_id):
        """Initialize a cover."""
        self._api = api
        self._unique_id = f"{gateway_id}-{cover.id}"
        self._cover = None
        self._cover_control = None
        self._cover_data = None
        self._name = None
        self._available = True
        self._gateway_id = gateway_id

        self._refresh(cover)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION

    @property
    def unique_id(self):
        """Return unique ID for cover."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        info = self._cover.device_info

        return {
            "identifiers": {(DOMAIN, self._cover.id)},
            "name": self._name,
            "manufacturer": info.manufacturer,
            "model": info.model_number,
            "sw_version": info.firmware_version,
            "via_device": (DOMAIN, self._gateway_id),
        }

    async def async_added_to_hass(self):
        """Start thread when added to hass."""
        self._async_start_observe()

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def should_poll(self):
        """No polling needed for tradfri cover."""
        return False

    @property
    def name(self):
        """Return the display name of this cover."""
        return self._name

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return 100 - self._cover_data.current_cover_position

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        await self._api(self._cover_control.set_state(100 - kwargs[ATTR_POSITION]))

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self._api(self._cover_control.set_state(0))

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        await self._api(self._cover_control.set_state(100))

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        return self.current_cover_position == 0

    @callback
    def _async_start_observe(self, exc=None):
        """Start observation of cover."""
        if exc:
            self._available = False
            self.async_schedule_update_ha_state()
            _LOGGER.warning("Observation failed for %s", self._name, exc_info=exc)
        try:
            cmd = self._cover.observe(
                callback=self._observe_update,
                err_callback=self._async_start_observe,
                duration=0,
            )
            self.hass.async_create_task(self._api(cmd))
        except PytradfriError as err:
            _LOGGER.warning("Observation failed, trying again", exc_info=err)
            self._async_start_observe()

    def _refresh(self, cover):
        """Refresh the cover data."""
        self._cover = cover

        # Caching of BlindControl and cover object
        self._available = cover.reachable
        self._cover_control = cover.blind_control
        self._cover_data = cover.blind_control.blinds[0]
        self._name = cover.name

    @callback
    def _observe_update(self, tradfri_device):
        """Receive new state data for this cover."""
        self._refresh(tradfri_device)
        self.async_schedule_update_ha_state()
