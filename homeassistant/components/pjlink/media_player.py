"""Support for controlling projector via the PJLink protocol."""
from __future__ import annotations

from pypjlink import MUTE_AUDIO, Projector
from pypjlink.projector import ProjectorError
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
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

ATTR_PROJECTOR_STATUS = "projector_status"
ATTR_LAMP_STATUS = "lamp_status"
ATTR_FAN_ERROR = "fan_error"
ATTR_LAMP_ERROR = "lamp_error"
ATTR_TEMP_ERROR = "temp_error"
ATTR_COVER_ERROR = "cover_error"
ATTR_FILTER_ERROR = "filter_error"
ATTR_OTHER_ERROR = "other_error"
ATTR_MANUFACTURER = "manufacturer"
ATTR_PRODUCT_NAME = "product_name"
ATTR_OTHER_INFO = "other_info"
ATTR_HAS_ERROR = "has_error"

ATTR_TO_PROPERTY = [
    ATTR_PROJECTOR_STATUS,
    ATTR_LAMP_STATUS,
    ATTR_FAN_ERROR,
    ATTR_LAMP_ERROR,
    ATTR_TEMP_ERROR,
    ATTR_COVER_ERROR,
    ATTR_FILTER_ERROR,
    ATTR_OTHER_ERROR,
    ATTR_MANUFACTURER,
    ATTR_OTHER_INFO,
    ATTR_HAS_ERROR,
]


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
        """Initialize the PJLink device."""
        self._host = host
        self._port = port
        self._name = name
        self._password = password
        self._encoding = encoding
        self._muted = False
        self._pwstate = MediaPlayerState.OFF
        self._current_source = None
        self._source_name_mapping = None
        self._source_list = None

        # Other projector data.
        self._raw_pwstate = "off"
        self._lamp_status = []
        self._fan_error = None
        self._lamp_error = None
        self._temp_error = None
        self._cover_error = None
        self._filter_error = None
        self._other_error = None
        self._manufacturer = None
        self._product_name = None
        self._other_info = None
        self._has_error = False

        with self.projector() as projector:
            self.update_metadata(projector)

    def update_metadata(self, projector):
        """Update projector metadata if metadata hasn't been set."""
        if not self._name:
            try:
                self._name = projector.get_name()
            except ProjectorError:
                pass

        if not self._manufacturer:
            try:
                self._manufacturer = projector.get_manufacturer()
            except ProjectorError:
                pass

        if not self._product_name:
            try:
                self._product_name = projector.get_product_name()
            except ProjectorError:
                pass

        if not self._source_list:
            try:
                inputs = projector.get_inputs()

                self._source_name_mapping = {format_input_source(*x): x for x in inputs}
                self._source_list = sorted(self._source_name_mapping.keys())
            except ProjectorError:
                pass

    def projector(self):
        """Create PJLink Projector instance."""
        projector = Projector.from_address(
            self._host, self._port, self._encoding, DEFAULT_TIMEOUT
        )

        projector.authenticate(self._password)

        return projector

    def update(self) -> None:
        """Get the latest state from the device."""
        with self.projector() as projector:
            try:
                pwstate = projector.get_power()

                self._raw_pwstate = pwstate

                if pwstate in ("on", "warm-up"):
                    self._pwstate = MediaPlayerState.ON
                    self._muted = projector.get_mute()[1]
                    self._current_source = format_input_source(*projector.get_input())
                else:
                    self._pwstate = MediaPlayerState.OFF
                    self._muted = False
                    self._current_source = None
            except KeyError as err:
                if str(err) == "'OK'":
                    self._pwstate = MediaPlayerState.OFF
                    self._muted = False
                    self._current_source = None
                else:
                    raise
            except ProjectorError as err:
                if str(err) == "unavailable time":
                    self._pwstate = MediaPlayerState.OFF
                    self._muted = False
                    self._current_source = None
                else:
                    raise

            if self._raw_pwstate == "on":
                # Try and update metadata; some projectors won't report data if they're not on.
                self.update_metadata(projector)

            try:
                lamps_state = []

                for lamp_hours, lamp_state in projector.get_lamps():
                    lamps_state.append(
                        {
                            "hours": lamp_hours,
                            "state": "on" if lamp_state else "off",
                        }
                    )

                self._lamp_status = lamps_state
            except ProjectorError:
                pass

            try:
                # Get errors.
                errors = projector.get_errors()

                # Keep track of any errors.
                self._has_error = False

                for key, value in errors.items():
                    if key == "temperature":
                        key = "temp"

                    # Clear error if error is "ok".
                    if value == "ok":
                        value = None
                    else:
                        self._has_error = True

                    # Ignore unsupported errors - none at the time of writing.
                    try:
                        setattr(self, f"_{key}_error", value)
                    except AttributeError:
                        pass
            except ProjectorError:
                pass

            # Get other info.
            try:
                self._other_info = projector.get_other_info()
            except ProjectorError:
                pass

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

    def turn_off(self) -> None:
        """Turn projector off."""
        with self.projector() as projector:
            projector.set_power("off")

    def turn_on(self) -> None:
        """Turn projector on."""
        with self.projector() as projector:
            projector.set_power("on")

    def mute_volume(self, mute: bool) -> None:
        """Mute (true) of unmute (false) media player."""
        with self.projector() as projector:
            projector.set_mute(MUTE_AUDIO, mute)

    def select_source(self, source: str) -> None:
        """Set the input source."""
        source = self._source_name_mapping[source]
        with self.projector() as projector:
            projector.set_input(*source)

    @property
    def extra_state_attributes(self):
        """Add the extra projector specific attributes."""
        state_attr = {}

        for attr in ATTR_TO_PROPERTY:
            if (value := getattr(self, attr)) is not None:
                state_attr[attr] = value

        return state_attr

    @property
    def projector_status(self):
        """Return the warming/on/cooling/off state of the device."""
        return self._raw_pwstate

    @property
    def lamp_status(self):
        """Return the lamp status of the device."""
        return self._lamp_status

    @property
    def fan_error(self):
        """Return the fan error, if any."""
        return self._fan_error

    @property
    def lamp_error(self):
        """Return the lamp error, if any."""
        return self._lamp_error

    @property
    def temp_error(self):
        """Return the temperature error, if any."""
        return self._temp_error

    @property
    def cover_error(self):
        """Return the cover error, if any."""
        return self._cover_error

    @property
    def filter_error(self):
        """Return the filter error, if any."""
        return self._filter_error

    @property
    def other_error(self):
        """Return the lamp error, if any."""
        return self._other_error

    @property
    def manufacturer(self):
        """Return the manufacturer."""
        return self._manufacturer

    @property
    def product_name(self):
        """Return the product name."""
        return self._product_name

    @property
    def other_info(self):
        """Return other information."""
        return self._other_info

    @property
    def has_error(self):
        """Return whether any errors are set."""
        return self._has_error
