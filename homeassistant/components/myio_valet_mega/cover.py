"""myIO Cover platform for the protected relay pairs."""
from datetime import timedelta
import logging

from myio.comms_thread import CommsThread  # pylint: disable=import-error

from homeassistant.components.cover import (
    DEVICE_CLASS_SHADE,
    STATE_CLOSING,
    STATE_OPENING,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_STOP,
    CoverDevice,
)
from homeassistant.const import CONF_NAME
from homeassistant.util import slugify

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=3)
SUPPORTED_FEATURES = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP
COMMS_THREAD = CommsThread()


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the myIO covers."""


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the myIO Covers config entry."""

    _server_name = slugify(config_entry.data[CONF_NAME])
    _server_status = hass.states.get(_server_name + ".state").state
    _server_data = hass.data[_server_name]
    _prots = _server_data["protection"]
    _cover_entities = []

    if _server_status.startswith("Online"):
        for _id in _prots:
            if 0 < _prots[_id]["element0"] <= 64 and 0 < _prots[_id]["element1"] <= 64:
                _cover_entities.append(MyIOCover(hass, config_entry, _id, _server_name))
    async_add_entities(_cover_entities, True)


class MyIOCover(CoverDevice):
    """Representation of a myIO cover."""

    def __init__(self, hass, config_entry, _id, _server_name):
        """Initialize the cover."""

        self._config_entry = config_entry
        self._server_name = _server_name
        self._server_data = hass.data[_server_name]
        self._server_status = hass.states.get(_server_name + ".state").state
        self._relay_up = str(self._server_data["protection"][str(_id)]["element0"])
        self._relay_down = str(self._server_data["protection"][str(_id)]["element1"])
        self._relay_up_d = str(
            self._server_data["relays"][str(int(self._relay_up) - 1)]["description"]
        )
        self._relay_down_d = str(
            self._server_data["relays"][str(int(self._relay_down) - 1)]["description"]
        )
        self._id = _id
        self.entity_id = f"cover.{_server_name}_{self._id}"
        self._state = None

        def longest_substring_finder(string1, string2):
            answer = ""
            len1, len2 = len(string1), len(string2)
            for i in range(len1):
                match = ""
                for j in range(len2):
                    if i + j < len1 and string1[i + j] == string2[j]:
                        match += string2[j]
                    else:
                        if len(match) > len(answer):
                            answer = match
                        match = ""
            return answer

        self._name = longest_substring_finder(self._relay_up_d, self._relay_down_d,)
        self.hass = hass
        self._unique_id = _id
        self._is_opening = False
        self._is_closing = False
        self._available = True
        self._supported_features = SUPPORTED_FEATURES
        self._device_class = DEVICE_CLASS_SHADE
        self._position = 50

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._server_name, self._unique_id)
            },
            "name": self.name,
        }

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self) -> bool:
        """Return availability."""
        return self._available

    @property
    def unique_id(self):
        """Return unique ID for cover."""
        return f"server name = {self._server_name}, id = {self._unique_id}"

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def should_poll(self):
        """Return true, Polling needed myIOCover for refreshing."""
        return True

    @property
    def is_closing(self):
        """Return if the cover is closing."""
        return self._is_closing

    @property
    def is_opening(self):
        """Return if the cover is opening."""
        return self._is_opening

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    def server_status(self):
        """Return the server status."""
        return self.hass.states.get(f"{self._server_name}.state").state

    def server_data(self):
        """Return the actual server data dictionary database."""
        return self.hass.data[self._server_name]

    async def send_post(self, post):
        """Send post to the myIO-server, and apply the response."""
        [
            self.hass.data[self._server_name],
            self._server_status,
        ] = await COMMS_THREAD.send(
            server_data=self.server_data(),
            server_status=self.server_status(),
            config_entry=self._config_entry,
            _post=post,
        )
        self.hass.states.async_set(f"{self._server_name}.state", self._server_status)
        return True

    async def async_close_cover(self, **kwargs):
        """Close the cover.Send the _post to the myIO server."""

        await self.send_post(f"r_OFF={self._relay_up}&r_ON={self._relay_down}")

        self._is_closing = True
        self._is_opening = False

        self.async_schedule_update_ha_state()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""

        await self.send_post(f"r_OFF={self._relay_down}&r_ON={self._relay_up}")

        self._is_opening = True
        self._is_closing = False

        self.async_schedule_update_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""

        self._is_closing = False
        self._is_opening = False

        await self.send_post(f"r_OFF={self._relay_up}&r_OFF={self._relay_down}")

        self.async_schedule_update_ha_state()

    async def async_update(self):
        """Fetch new state data for the sensor."""

        self._server_data = self.hass.data[self._server_name]
        if self.hass.states.get(self._server_name + ".state").state.startswith(
            "Online"
        ):
            self._available = True
        else:
            self._available = False
        # check relay's state
        _relays = self._server_data["relays"]
        self._is_opening = _relays[str(int(self._relay_up) - 1)]["state"]
        self._is_closing = _relays[str(int(self._relay_down) - 1)]["state"]
        if self._is_opening:
            self._state = STATE_OPENING
        elif self._is_closing:
            self._state = STATE_CLOSING
        else:
            self._state = None
