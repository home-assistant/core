"""Support for Broadlink RM device gateway for IR/RF covers."""
from datetime import timedelta
from ipaddress import ip_address
import logging
import socket

import broadlink
import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
    SUPPORT_STOP_TILT,
    CoverDevice,
)
from homeassistant.const import (
    CONF_COMMAND_CLOSE,
    CONF_COMMAND_OPEN,
    CONF_COMMAND_STOP,
    CONF_COVERS,
    CONF_FRIENDLY_NAME,
    CONF_HOST,
    CONF_MAC,
    CONF_TIMEOUT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.util import slugify
from homeassistant.util.dt import utcnow

from . import async_setup_service, data_packet, hostname, mac_address

_LOGGER = logging.getLogger(__name__)

CONF_OPENING_TIME = "opening_time"
CONF_CLOSING_TIME = "closing_time"
CONF_START_POS = "start_pos"

CONF_TILT_COMMAND_OPEN = "tilt_command_open"
CONF_TILT_COMMAND_CLOSE = "tilt_command_close"
CONF_TILT_COMMAND_STOP = "tilt_command_stop"
CONF_TILT_OPENING_TIME = "tilt_opening_time"
CONF_TILT_CLOSING_TIME = "tilt_closing_time"
CONF_TILT_START_POS = "tilt_start_pos"

DEVICE_DEFAULT_NAME = "Broadlink cover"
DEFAULT_TIMEOUT = 5
DEFAULT_RETRY = 3
DEFAULT_PORT = 80
DEVICE_SIMULATION = False

DEFAULT_TRAVEL_TIME = 2
MAX_TRAVEL_TIME = 120
POSITION_MIN = 0
POSITION_MAX = 100
DEFAULT_START_POS = 0

TRAVEL_TIME = vol.All(vol.Coerce(float), vol.Range(min=0, max=MAX_TRAVEL_TIME))

COVER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_COMMAND_OPEN): data_packet,
        vol.Optional(CONF_COMMAND_CLOSE): data_packet,
        vol.Optional(CONF_COMMAND_STOP): data_packet,
        vol.Optional(CONF_OPENING_TIME, default=0.0): TRAVEL_TIME,
        vol.Optional(CONF_CLOSING_TIME, default=0.0): TRAVEL_TIME,
        vol.Optional(CONF_START_POS, default=DEFAULT_START_POS): cv.positive_int,
        vol.Optional(CONF_TILT_COMMAND_OPEN): data_packet,
        vol.Optional(CONF_TILT_COMMAND_CLOSE): data_packet,
        vol.Optional(CONF_TILT_COMMAND_STOP): data_packet,
        vol.Optional(CONF_TILT_OPENING_TIME, default=0.0): TRAVEL_TIME,
        vol.Optional(CONF_TILT_CLOSING_TIME, default=0.0): TRAVEL_TIME,
        vol.Optional(CONF_TILT_START_POS, default=DEFAULT_START_POS): cv.positive_int,
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): vol.All(vol.Any(hostname, ip_address), cv.string),
        vol.Required(CONF_MAC): mac_address,
        vol.Optional(CONF_FRIENDLY_NAME, default=DEVICE_DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_COVERS, default={}): vol.Schema({cv.slug: COVER_SCHEMA}),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Broadlink covers."""
    host = config[CONF_HOST]
    mac_addr = config[CONF_MAC]
    timeout = config[CONF_TIMEOUT]
    if DEVICE_SIMULATION:
        broadlink_device = None
    else:
        broadlink_device = broadlink.rm((host, DEFAULT_PORT), mac_addr, None)
        broadlink_device.timeout = timeout
        try:
            broadlink_device.auth()
        except socket.timeout:
            _LOGGER.error("Failed to connect to device")
        hass.add_job(async_setup_service, hass, host, broadlink_device)

    devices = config.get(CONF_COVERS)
    covers = []
    for object_id, device_config in devices.items():
        covers.append(
            BroadlinkRMCover(
                object_id,
                device_config.get(CONF_FRIENDLY_NAME, object_id),
                broadlink_device,
                device_config.get(CONF_COMMAND_OPEN),
                device_config.get(CONF_COMMAND_CLOSE),
                device_config.get(CONF_COMMAND_STOP),
                device_config.get(CONF_OPENING_TIME),
                device_config.get(CONF_CLOSING_TIME),
                device_config.get(CONF_START_POS),
                device_config.get(CONF_TILT_COMMAND_OPEN),
                device_config.get(CONF_TILT_COMMAND_CLOSE),
                device_config.get(CONF_TILT_COMMAND_STOP),
                device_config.get(CONF_TILT_OPENING_TIME),
                device_config.get(CONF_TILT_CLOSING_TIME),
                device_config.get(CONF_TILT_START_POS),
            )
        )
    add_entities(covers)


class BroadlinkRMCover(CoverDevice):
    """Representation of an Broadlink cover."""

    def __init__(
        self,
        name,
        friendly_name,
        device,
        command_open,
        command_close,
        command_stop,
        opening_time,
        closing_time,
        start_pos,
        tilt_command_open,
        tilt_command_close,
        tilt_command_stop,
        tilt_opening_time,
        tilt_closing_time,
        tilt_start_pos,
    ):
        """Initialize the cover."""
        self.entity_id = ENTITY_ID_FORMAT.format(slugify(name))
        self._name = friendly_name

        self._supported_features = 0
        if command_open and command_close:
            self._supported_features = SUPPORT_OPEN | SUPPORT_CLOSE
            if command_stop:
                self._supported_features |= SUPPORT_STOP
                if (opening_time > 0) and (closing_time > 0):
                    self._supported_features |= SUPPORT_SET_POSITION

        if tilt_command_open and tilt_command_close:
            self._supported_features |= SUPPORT_OPEN_TILT | SUPPORT_CLOSE_TILT
            if tilt_command_stop:
                self._supported_features |= SUPPORT_STOP_TILT
                if (tilt_opening_time > 0) and (tilt_closing_time > 0):
                    self._supported_features |= SUPPORT_SET_TILT_POSITION

        self._main = _subCover(
            self,
            self.entity_id,
            self.name,
            False,
            device,
            command_open,
            command_close,
            command_stop,
            opening_time,
            closing_time,
            start_pos,
        )

        self._tilt = _subCover(
            self,
            self.entity_id,
            self.name,
            True,
            device,
            tilt_command_open,
            tilt_command_close,
            tilt_command_stop,
            tilt_opening_time,
            tilt_closing_time,
            tilt_start_pos,
        )

        _LOGGER.debug("Init done %s", self._name)

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return True

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return self._main.current_cover_position

    @property
    def current_cover_tilt_position(self):
        """Return the current tilt position of the cover."""
        return self._tilt.current_cover_position

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._main.is_closed

    @property
    def is_closing(self):
        """Return if the cover is closing."""
        return self._main.is_closing

    @property
    def is_opening(self):
        """Return if the cover is opening."""
        return self._main.is_opening

    def close_cover(self, **kwargs):
        """Close the cover."""
        self._main.close_cover(**kwargs)

    def close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        self._tilt.close_cover(**kwargs)

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._main.open_cover(**kwargs)

    def open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        self._tilt.open_cover(**kwargs)

    def stop_cover(self, **kwargs):
        """Stop the cover on command."""
        self._main.stop_cover(**kwargs)

    def stop_cover_tilt(self, **kwargs):
        """Stop the cover tilt."""
        self._tilt.stop_cover(**kwargs)

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        self._main.set_cover_position(**kwargs)

    def set_cover_tilt_position(self, **kwargs):
        """Move the cover til to a specific position."""
        self._tilt.set_cover_position(**kwargs)


class _subCover:
    """Half Broadlink cover - main or tilt."""

    def __init__(
        self,
        parent,
        entity_id,
        name,
        is_tilt,
        device,
        command_open,
        command_close,
        command_stop,
        opening_time,
        closing_time,
        start_pos,
    ):
        """Initialize the cover."""
        self._parent = parent
        self.entity_id = entity_id
        self._device = device
        self._name = name + (" (tilt)" if is_tilt else "")
        self._is_tilt = is_tilt

        self._command_open = command_open
        self._command_close = command_close
        self._command_stop = command_stop

        if opening_time > 0:
            self._opening_speed = float(POSITION_MAX) / opening_time
        else:
            self._opening_speed = float(POSITION_MAX) / DEFAULT_TRAVEL_TIME

        if closing_time > 0:
            self._closing_speed = float(-POSITION_MAX) / closing_time
        else:
            self._closing_speed = float(-POSITION_MAX) / DEFAULT_TRAVEL_TIME

        self._position = start_pos
        self._position_set = self._position
        self._position_start = self._position
        self._closing_direction = True
        self._unsub_listener_cover = None
        self._is_opening = False
        self._is_closing = False
        self._speed = None
        if self._position is None:
            self._closed = None
        else:
            self._closed = self._position <= POSITION_MIN
        self._travel_time_start = None
        self._travel_time_stop = None

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return self._position

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._closed

    @property
    def is_closing(self):
        """Return if the cover is closing."""
        return self._is_closing

    @property
    def is_opening(self):
        """Return if the cover is opening."""
        return self._is_opening

    def close_cover(self, **kwargs):
        """Close the cover."""
        _LOGGER.debug("Cover: %s - closing", self._name)

        if self._sendpacket(self._command_close):
            self._is_closing = True
            self._closing_direction = True
            self._position_set = POSITION_MIN
            self._listen_cover()
            self._parent.schedule_update_ha_state()

    def open_cover(self, **kwargs):
        """Open the cover."""
        _LOGGER.debug("Cover: %s - Opening", self._name)

        if self._sendpacket(self._command_open):
            self._is_opening = True
            self._closing_direction = False
            self._position_set = POSITION_MAX
            self._listen_cover()
            self._parent.schedule_update_ha_state()

    def stop_cover(self, **kwargs):
        """Stop the cover on command."""
        _LOGGER.debug("Cover: %s - Stopping", self._name)

        if self._sendpacket(self._command_stop):
            if self._unsub_listener_cover is not None:
                self._unsub_listener_cover()
                self._unsub_listener_cover = None

            self._update_position(utcnow())

            self._position_set = self._position
            self._position_start = None
            self._is_opening = False
            self._is_closing = False
            if self._position is not None:
                self._closed = self._position <= POSITION_MIN

            self._parent.schedule_update_ha_state()

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = (
            kwargs.get(ATTR_TILT_POSITION)
            if self._is_tilt
            else kwargs.get(ATTR_POSITION)
        )
        position = max(POSITION_MIN, min(round(position, 0), POSITION_MAX))

        if position == POSITION_MIN:
            return self.close_cover()

        if position == POSITION_MAX:
            return self.open_cover()

        if self._position is None:
            return

        if self._position == position:
            return

        _LOGGER.debug("Cover: %s - Set position: %i", self._name, position)

        self._position_set = position
        self._closing_direction = self._position_set < self._position
        if self._closing_direction:
            command = self._command_close
        else:
            command = self._command_open

        if self._sendpacket(command):
            self._listen_cover()
            self._parent.schedule_update_ha_state()

    def _listen_cover(self):
        """Listen for changes in cover."""
        if self._unsub_listener_cover is not None:
            self._unsub_listener_cover()
            self._unsub_listener_cover = None
            self._update_position(utcnow())

        self._travel_time_start = utcnow()
        self._speed = (
            self._closing_speed if self._closing_direction else self._opening_speed
        )
        travel_time = abs((self._position_set - self._position) / self._speed)
        self._travel_time_stop = self._travel_time_start + timedelta(
            seconds=travel_time
        )
        self._position_start = self._position

        _LOGGER.debug(
            "Cover: %s - Moving from : %i, to: %i, in: %.3f",
            self._name,
            self._position_start,
            self._position_set,
            travel_time,
        )

        if self._unsub_listener_cover is None:
            self._unsub_listener_cover = track_utc_time_change(
                self._parent.hass, self._time_changed_cover
            )

    def _time_changed_cover(self, now):
        """Track cover position over time."""
        remaining_time = self._travel_time_stop - now
        if round(remaining_time.total_seconds()) > 0:
            self._update_position(now)
        else:
            if self._position_set not in [POSITION_MIN, POSITION_MAX]:
                self._sendpacket(self._command_stop)

            if self._unsub_listener_cover is not None:
                self._unsub_listener_cover()
                self._unsub_listener_cover = None

            self._update_position(now)

            _LOGGER.debug(
                "Cover: %s - Travel ended after : %.3f",
                self._name,
                (now - self._travel_time_start).total_seconds(),
            )

            if self._position_set == POSITION_MIN:
                self._position = POSITION_MIN
            elif self._position_set == POSITION_MAX:
                self._position = POSITION_MAX

            self._position_start = None
            self._is_opening = False
            self._is_closing = False
            if self._position is not None:
                self._closed = self._position <= POSITION_MIN

        self._parent.schedule_update_ha_state()

    def _update_position(self, now):
        """Compute actual position based on travelling time."""
        if self._position_start is None or self._travel_time_start is None:
            return

        travel_time = now - self._travel_time_start
        travel_pos = round(travel_time.total_seconds() * self._speed)
        position = self._position_start + travel_pos
        self._position = max(POSITION_MIN, min(position, POSITION_MAX))
        self._closed = self._position <= POSITION_MIN

        _LOGGER.debug("Cover: %s - Position is: %i ", self._name, self._position)

    def _sendpacket(self, packet, retry=2):
        """Send packet to device."""
        if self._device is None:
            _LOGGER.debug("Simulation - send packet")
            return True

        if packet is None:
            _LOGGER.debug("Empty packet")
            return True
        try:
            self._device.send_data(packet)
        except (socket.timeout, ValueError) as error:
            if retry < 1:
                _LOGGER.error(error)
                return False
            if not self._auth():
                return False
            return self._sendpacket(packet, retry - 1)
        return True

    def _auth(self, retry=2):
        if self._device is None:
            _LOGGER.debug("Simulation - authorization")
            return True
        try:
            auth = self._device.auth()
        except socket.timeout:
            auth = False
            if retry < 1:
                _LOGGER.error("Timeout during authorization")
        if not auth and retry > 0:
            return self._auth(retry - 1)
        return auth
