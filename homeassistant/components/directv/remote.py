"""Support for the DIRECTV remote."""
import logging
from typing import Callable, List

from DirectPy import DIRECTV
from requests.exceptions import RequestException

from homeassistant.components.remote import RemoteDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    DATA_CLIENT,
    DATA_LOCATIONS,
    DATA_VERSION_INFO,
    DEFAULT_MANUFACTURER,
    DOMAIN,
    MODEL_CLIENT,
    MODEL_HOST,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List, bool], None],
) -> bool:
    """Load DirecTV remote based on a config entry."""
    locations = hass.data[DOMAIN][entry.entry_id][DATA_LOCATIONS]
    version_info = hass.data[DOMAIN][entry.entry_id][DATA_VERSION_INFO]
    entities = []

    for loc in locations["locations"]:
        if "locationName" not in loc or "clientAddr" not in loc:
            continue

        if loc["clientAddr"] != "0":
            dtv = DIRECTV(
                entry.data[CONF_HOST],
                DEFAULT_PORT,
                loc["clientAddr"],
                determine_state=False,
            )
        else:
            dtv = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]

        entities.append(
            DirecTvRemote(
                str.title(loc["locationName"]), loc["clientAddr"], dtv, version_info,
            )
        )

    async_add_entities(entities, True)


class DirecTvRemote(RemoteDevice):
    """Device that sends commands to a DirecTV receiver."""

    def __init__(
        self,
        name: str,
        device: str,
        dtv: DIRECTV,
        version_info: Optional[Dict] = None,
    ):
        """Initialize the DirecTV device."""
        self.dtv = dtv
        self._name = name
        self._unique_id = None
        self._is_client = device != "0"
        self._receiver_id = None
        self._software_version = None

        if self._is_client:
            self._model = MODEL_CLIENT
            self._unique_id = device

        if version_info:
            self._receiver_id = "".join(version_info["receiverId"].split())

            if not self._is_client:
                self._unique_id = self._receiver_id
                self._model = MODEL_HOST
                self._software_version = version_info["stbSoftwareVersion"]

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "name": self.name,
            "identifiers": {(DOMAIN, self.unique_id)},
            "manufacturer": DEFAULT_MANUFACTURER,
            "model": self._model,
            "sw_version": self._software_version,
            "via_device": (DOMAIN, self._receiver_id),
        }

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    def _send_key(self, key):
        """Send a key press command.

        Supported keys: power, poweron, poweroff, format,
        pause, rew, replay, stop, advance, ffwd, record,
        play, guide, active, list, exit, back, menu, info,
        up, down, left, right, select, red, green, yellow,
        blue, chanup, chandown, prev, 0, 1, 2, 3, 4, 5,
        6, 7, 8, 9, dash, enter
        """
        _LOGGER.debug("Sending key: '%s'", key)
        try:
            self.dtv.key_press(key)
        except RequestException as ex:
            _LOGGER.error(
                "Transmit of key failed, %s, exception: %s", key, ex
            )

    def send_command(self, command, **kwargs):
        """Send a command to a device."""
        for single_command in command:
            self._send_key(single_command)
