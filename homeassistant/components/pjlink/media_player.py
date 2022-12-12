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

from .const import (
    _LOGGER,
    CONF_ENCODING,
    DEFAULT_ENCODING,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

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

    device = PjLinkDevice(host, port, name, encoding, password, config.get("unique_id"))
    hass_data[device_label] = device
    add_entities([device], True)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up platform."""
    setup_platform(hass, config, async_add_entities)


def format_input_source(input_source_name, input_source_number):
    """Format input source for display in UI."""
    return f"{input_source_name} {input_source_number}"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the config entry."""

    unique_id = config_entry.unique_id

    if unique_id is None:
        # How to generate a unique ID?
        # The PJLink API does not expose MAC address or serial number, only name, manufacturer, and model
        # Can we get the MAC address from the IP address?

        unique_id = config_entry.entry_id

        hass.config_entries.async_update_entry(
            config_entry, data={**config_entry.data, "unique_id": unique_id}
        )
        _LOGGER.debug("===== setting pjlink unique_id: %s ", unique_id)

    encoding = None
    if CONF_ENCODING in config_entry.data:
        encoding = config_entry.data[CONF_ENCODING]
    name = None
    if CONF_NAME in config_entry.data:
        name = config_entry.data[CONF_NAME]
    password = None
    if CONF_PASSWORD in config_entry.data:
        password = config_entry.data[CONF_PASSWORD]
    port = None
    if CONF_PORT in config_entry.data:
        port = config_entry.data[CONF_PORT]

    device = PjLinkDevice(
        host=config_entry.data[CONF_HOST],
        port=port,
        name=name,
        encoding=encoding,
        password=password,
        unique_id=unique_id,
    )

    async_add_entities([device], True)


class PjLinkDevice(MediaPlayerEntity):
    """Representation of a PJLink device."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, host, port, name, encoding, password, unique_id):
        """Iinitialize the PJLink device."""
        _LOGGER.debug("===> Initializing PjLinkDevice <===")
        self._host = host
        self._port = port
        self._attr_name = name
        self._password = password
        self._encoding = encoding
        self._unique_id = unique_id
        self._attr_is_volume_muted = False
        self._attr_state = MediaPlayerState.OFF
        with self.projector() as projector:
            if not self._attr_name:
                self._attr_name = projector.get_name()
            inputs = projector.get_inputs()
        self._source_name_mapping = {format_input_source(*x): x for x in inputs}
        self._attr_source_list = sorted(self._source_name_mapping.keys())

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
                if pwstate in ("on", "warm-up"):
                    self._attr_state = MediaPlayerState.ON
                    self._attr_is_volume_muted = projector.get_mute()[1]
                    self._attr_source = format_input_source(*projector.get_input())
                else:
                    self._attr_state = MediaPlayerState.OFF
                    self._attr_is_volume_muted = False
                    self._attr_source = None
            except KeyError as err:
                if str(err) == "'OK'":
                    self._attr_state = MediaPlayerState.OFF
                    self._attr_is_volume_muted = False
                    self._attr_source = None
                else:
                    raise
            except ProjectorError as err:
                if str(err) == "unavailable time":
                    self._attr_state = MediaPlayerState.OFF
                    self._attr_is_volume_muted = False
                    self._attr_source = None
                else:
                    raise

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
