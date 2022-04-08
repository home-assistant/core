"""Support for controlling projector via the PJLink protocol."""
from __future__ import annotations

from pypjlink import MUTE_AUDIO, Projector
from pypjlink.projector import ProjectorError
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

CONF_ENCODING = "encoding"

DEFAULT_PORT = 4352
DEFAULT_ENCODING = "utf-8"
DEFAULT_TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the PJLink platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    encoding = config.get(CONF_ENCODING)
    password = config.get(CONF_PASSWORD)

    if "pjlink" not in hass.data:
        hass.data["pjlink"] = {}
    hass_data = hass.data["pjlink"]

    device_label = f"{host}:{port}"
    if device_label in hass_data:
        return

    device = PjLinkDevice(host, port, name, encoding, password)
    hass_data[device_label] = device
    add_entities([device], True)


def format_input_source(input_source_name, input_source_number):
    """Format input source for display in UI."""
    return f"{input_source_name} {input_source_number}"


class PjLinkDevice(MediaPlayerEntity):
    """Representation of a PJLink device."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, host, port, name, encoding, password):
        """Iinitialize the PJLink device."""
        self._host = host
        self._port = port
        self._name = name
        self._password = password
        self._encoding = encoding
        self._muted = False
        self._pwstate = STATE_OFF
        self._current_source = None
        with self.projector() as projector:
            if not self._name:
                self._name = projector.get_name()
            inputs = projector.get_inputs()
        self._source_name_mapping = {format_input_source(*x): x for x in inputs}
        self._source_list = sorted(self._source_name_mapping.keys())

    def projector(self):
        """Create PJLink Projector instance."""

        projector = Projector.from_address(
            self._host, self._port, self._encoding, DEFAULT_TIMEOUT
        )
        projector.authenticate(self._password)
        return projector

    def update(self):
        """Get the latest state from the device."""

        with self.projector() as projector:
            try:
                pwstate = projector.get_power()
                if pwstate in ("on", "warm-up"):
                    self._pwstate = STATE_ON
                    self._muted = projector.get_mute()[1]
                    self._current_source = format_input_source(*projector.get_input())
                else:
                    self._pwstate = STATE_OFF
                    self._muted = False
                    self._current_source = None
            except KeyError as err:
                if str(err) == "'OK'":
                    self._pwstate = STATE_OFF
                    self._muted = False
                    self._current_source = None
                else:
                    raise
            except ProjectorError as err:
                if str(err) == "unavailable time":
                    self._pwstate = STATE_OFF
                    self._muted = False
                    self._current_source = None
                else:
                    raise

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._pwstate

    @property
    def is_volume_muted(self):
        """Return boolean indicating mute status."""
        return self._muted

    @property
    def source(self):
        """Return current input source."""
        return self._current_source

    @property
    def source_list(self):
        """Return all available input sources."""
        return self._source_list

    def turn_off(self):
        """Turn projector off."""
        with self.projector() as projector:
            projector.set_power("off")

    def turn_on(self):
        """Turn projector on."""
        with self.projector() as projector:
            projector.set_power("on")

    def mute_volume(self, mute):
        """Mute (true) of unmute (false) media player."""
        with self.projector() as projector:
            projector.set_mute(MUTE_AUDIO, mute)

    def select_source(self, source):
        """Set the input source."""
        source = self._source_name_mapping[source]
        with self.projector() as projector:
            projector.set_input(*source)
