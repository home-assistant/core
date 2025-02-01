"""Platform for the Garadget cover component."""

from __future__ import annotations

import logging
from typing import Any

import requests
import voluptuous as vol

from homeassistant.components.cover import (
    PLATFORM_SCHEMA as COVER_PLATFORM_SCHEMA,
    CoverDeviceClass,
    CoverEntity,
    CoverState,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_COVERS,
    CONF_DEVICE,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTR_AVAILABLE = "available"
ATTR_SENSOR_STRENGTH = "sensor_reflection_rate"
ATTR_SIGNAL_STRENGTH = "wifi_signal_strength"
ATTR_TIME_IN_STATE = "time_in_state"

DEFAULT_NAME = "Garadget"

STATE_OFFLINE = "offline"
STATE_STOPPED = "stopped"

STATES_MAP = {
    "open": CoverState.OPEN,
    "opening": CoverState.OPENING,
    "closed": CoverState.CLOSED,
    "closing": CoverState.CLOSING,
    "stopped": STATE_STOPPED,
}

COVER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ACCESS_TOKEN): cv.string,
        vol.Optional(CONF_DEVICE): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
    }
)

PLATFORM_SCHEMA = COVER_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_COVERS): cv.schema_with_slug_keys(COVER_SCHEMA)}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Garadget covers."""
    covers = []
    devices = config[CONF_COVERS]

    for device_id, device_config in devices.items():
        args = {
            "name": device_config.get(CONF_NAME),
            "device_id": device_config.get(CONF_DEVICE, device_id),
            "username": device_config.get(CONF_USERNAME),
            "password": device_config.get(CONF_PASSWORD),
            "access_token": device_config.get(CONF_ACCESS_TOKEN),
        }

        covers.append(GaradgetCover(hass, args))

    add_entities(covers)


class GaradgetCover(CoverEntity):
    """Representation of a Garadget cover."""

    _attr_device_class = CoverDeviceClass.GARAGE

    def __init__(self, hass, args):
        """Initialize the cover."""
        self.particle_url = "https://api.particle.io"
        self.hass = hass
        self._name = args["name"]
        self.device_id = args["device_id"]
        self.access_token = args["access_token"]
        self.obtained_token = False
        self._username = args["username"]
        self._password = args["password"]
        self._state = None
        self.time_in_state = None
        self.signal = None
        self.sensor = None
        self._unsub_listener_cover = None
        self._available = True

        if self.access_token is None:
            self.access_token = self.get_token()
            self._obtained_token = True

        try:
            if self._name is None:
                doorconfig = self._get_variable("doorConfig")
                if doorconfig["nme"] is not None:
                    self._name = doorconfig["nme"]
            self.update()
        except requests.exceptions.ConnectionError as ex:
            _LOGGER.error("Unable to connect to server: %(reason)s", {"reason": ex})
            self._state = STATE_OFFLINE
            self._available = False
            self._name = DEFAULT_NAME
        except KeyError:
            _LOGGER.warning(
                "Garadget device %(device)s seems to be offline",
                {"device": self.device_id},
            )
            self._name = DEFAULT_NAME
            self._state = STATE_OFFLINE
            self._available = False

    def __del__(self):
        """Try to remove token."""
        if self._obtained_token is True and self.access_token is not None:
            self.remove_token()

    @property
    def name(self) -> str:
        """Return the name of the cover."""
        return self._name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        data = {}

        if self.signal is not None:
            data[ATTR_SIGNAL_STRENGTH] = self.signal

        if self.time_in_state is not None:
            data[ATTR_TIME_IN_STATE] = self.time_in_state

        if self.sensor is not None:
            data[ATTR_SENSOR_STRENGTH] = self.sensor

        if self.access_token is not None:
            data[CONF_ACCESS_TOKEN] = self.access_token

        return data

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._state is None:
            return None
        return self._state == CoverState.CLOSED

    def get_token(self):
        """Get new token for usage during this session."""
        args = {
            "grant_type": "password",
            "username": self._username,
            "password": self._password,
        }
        url = f"{self.particle_url}/oauth/token"
        ret = requests.post(url, auth=("particle", "particle"), data=args, timeout=10)

        try:
            return ret.json()["access_token"]
        except KeyError:
            _LOGGER.error("Unable to retrieve access token")

    def remove_token(self):
        """Remove authorization token from API."""
        url = f"{self.particle_url}/v1/access_tokens/{self.access_token}"
        ret = requests.delete(url, auth=(self._username, self._password), timeout=10)
        return ret.text

    def _start_watcher(self, command):
        """Start watcher."""
        _LOGGER.debug("Starting Watcher for command: %s ", command)
        if self._unsub_listener_cover is None:
            self._unsub_listener_cover = track_utc_time_change(
                self.hass, self._check_state
            )

    def _check_state(self, now):
        """Check the state of the service during an operation."""
        self.schedule_update_ha_state(True)

    def close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        if self._state not in ["close", "closing"]:
            self._put_command("setState", "close")
            self._start_watcher("close")

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if self._state not in ["open", "opening"]:
            self._put_command("setState", "open")
            self._start_watcher("open")

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the door where it is."""
        if self._state not in ["stopped"]:
            self._put_command("setState", "stop")
            self._start_watcher("stop")

    def update(self) -> None:
        """Get updated status from API."""
        try:
            status = self._get_variable("doorStatus")
            _LOGGER.debug("Current Status: %s", status["status"])
            self._state = STATES_MAP.get(status["status"])
            self.time_in_state = status["time"]
            self.signal = status["signal"]
            self.sensor = status["sensor"]
            self._available = True
        except requests.exceptions.ConnectionError as ex:
            _LOGGER.error("Unable to connect to server: %(reason)s", {"reason": ex})
            self._state = STATE_OFFLINE
        except KeyError:
            _LOGGER.warning(
                "Garadget device %(device)s seems to be offline",
                {"device": self.device_id},
            )
            self._state = STATE_OFFLINE

        if (
            self._state not in [CoverState.CLOSING, CoverState.OPENING]
            and self._unsub_listener_cover is not None
        ):
            self._unsub_listener_cover()
            self._unsub_listener_cover = None

    def _get_variable(self, var):
        """Get latest status."""
        url = f"{self.particle_url}/v1/devices/{self.device_id}/{var}?access_token={self.access_token}"
        ret = requests.get(url, timeout=10)
        result = {}
        for pairs in ret.json()["result"].split("|"):
            key = pairs.split("=")
            result[key[0]] = key[1]
        return result

    def _put_command(self, func, arg=None):
        """Send commands to API."""
        params = {"access_token": self.access_token}
        if arg:
            params["command"] = arg
        url = f"{self.particle_url}/v1/devices/{self.device_id}/{func}"
        ret = requests.post(url, data=params, timeout=10)
        return ret.json()
