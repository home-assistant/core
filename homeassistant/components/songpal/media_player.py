"""Support for Songpal-enabled (Sony) media devices."""
import asyncio
from collections import OrderedDict
import logging

from songpal import (
    ConnectChange,
    ContentChange,
    Device,
    PowerChange,
    SongpalException,
    VolumeChange,
)
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerDevice
from homeassistant.components.media_player.const import (
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, SET_SOUND_SETTING

_LOGGER = logging.getLogger(__name__)

CONF_ENDPOINT = "endpoint"

PARAM_NAME = "name"
PARAM_VALUE = "value"

PLATFORM = "songpal"

SUPPORT_SONGPAL = (
    SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME): cv.string, vol.Required(CONF_ENDPOINT): cv.string}
)

SET_SOUND_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(PARAM_NAME): cv.string,
        vol.Required(PARAM_VALUE): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Songpal platform."""
    if PLATFORM not in hass.data:
        hass.data[PLATFORM] = {}

    if discovery_info is not None:
        name = discovery_info["name"]
        endpoint = discovery_info["properties"]["endpoint"]
        _LOGGER.debug("Got autodiscovered %s - endpoint: %s", name, endpoint)

        device = SongpalDevice(name, endpoint)
    else:
        name = config.get(CONF_NAME)
        endpoint = config.get(CONF_ENDPOINT)
        device = SongpalDevice(name, endpoint, poll=False)

    if endpoint in hass.data[PLATFORM]:
        _LOGGER.debug("The endpoint exists already, skipping setup.")
        return

    try:
        await device.initialize()
    except SongpalException as ex:
        _LOGGER.error("Unable to get methods from songpal: %s", ex)
        raise PlatformNotReady

    hass.data[PLATFORM][endpoint] = device

    async_add_entities([device], True)

    async def async_service_handler(service):
        """Service handler."""
        entity_id = service.data.get("entity_id", None)
        params = {
            key: value for key, value in service.data.items() if key != ATTR_ENTITY_ID
        }

        for device in hass.data[PLATFORM].values():
            if device.entity_id == entity_id or entity_id is None:
                _LOGGER.debug(
                    "Calling %s (entity: %s) with params %s", service, entity_id, params
                )

                await device.async_set_sound_setting(
                    params[PARAM_NAME], params[PARAM_VALUE]
                )

    hass.services.async_register(
        DOMAIN, SET_SOUND_SETTING, async_service_handler, schema=SET_SOUND_SCHEMA
    )


class SongpalDevice(MediaPlayerDevice):
    """Class representing a Songpal device."""

    def __init__(self, name, endpoint, poll=False):
        """Init."""
        self._name = name
        self._endpoint = endpoint
        self._poll = poll
        self.dev = Device(self._endpoint)
        self._sysinfo = None

        self._state = False
        self._available = False
        self._initialized = False

        self._volume_control = None
        self._volume_min = 0
        self._volume_max = 1
        self._volume = 0
        self._is_muted = False

        self._active_source = None
        self._sources = {}

    @property
    def should_poll(self):
        """Return True if the device should be polled."""
        return self._poll

    async def initialize(self):
        """Initialize the device."""
        await self.dev.get_supported_methods()
        self._sysinfo = await self.dev.get_system_info()

    async def async_activate_websocket(self):
        """Activate websocket for listening if wanted."""
        _LOGGER.info("Activating websocket connection..")

        async def _volume_changed(volume: VolumeChange):
            _LOGGER.debug("Volume changed: %s", volume)
            self._volume = volume.volume
            self._is_muted = volume.mute
            self.async_write_ha_state()

        async def _source_changed(content: ContentChange):
            _LOGGER.debug("Source changed: %s", content)
            if content.is_input:
                self._active_source = self._sources[content.source]
                _LOGGER.debug("New active source: %s", self._active_source)
                self.async_write_ha_state()
            else:
                _LOGGER.debug("Got non-handled content change: %s", content)

        async def _power_changed(power: PowerChange):
            _LOGGER.debug("Power changed: %s", power)
            self._state = power.status
            self.async_write_ha_state()

        async def _try_reconnect(connect: ConnectChange):
            _LOGGER.error(
                "Got disconnected with %s, trying to reconnect.", connect.exception
            )
            self._available = False
            self.dev.clear_notification_callbacks()
            self.async_write_ha_state()

            # Try to reconnect forever, a successful reconnect will initialize
            # the websocket connection again.
            delay = 10
            while not self._available:
                _LOGGER.debug("Trying to reconnect in %s seconds", delay)
                await asyncio.sleep(delay)
                # We need to inform HA about the state in case we are coming
                # back from a disconnected state.
                await self.async_update_ha_state(force_refresh=True)
                delay = min(2 * delay, 300)

            _LOGGER.info("Reconnected to %s", self.name)

        self.dev.on_notification(VolumeChange, _volume_changed)
        self.dev.on_notification(ContentChange, _source_changed)
        self.dev.on_notification(PowerChange, _power_changed)
        self.dev.on_notification(ConnectChange, _try_reconnect)

        async def listen_events():
            await self.dev.listen_notifications()

        async def handle_stop(event):
            await self.dev.stop_listen_notifications()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, handle_stop)

        self.hass.loop.create_task(listen_events())

    @property
    def name(self):
        """Return name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._sysinfo.macAddr

    @property
    def available(self):
        """Return availability of the device."""
        return self._available

    async def async_set_sound_setting(self, name, value):
        """Change a setting on the device."""
        await self.dev.set_sound_settings(name, value)

    async def async_update(self):
        """Fetch updates from the device."""
        try:
            volumes = await self.dev.get_volume_information()
            if not volumes:
                _LOGGER.error("Got no volume controls, bailing out")
                self._available = False
                return

            if len(volumes) > 1:
                _LOGGER.debug("Got %s volume controls, using the first one", volumes)

            volume = volumes[0]
            _LOGGER.debug("Current volume: %s", volume)

            self._volume_max = volume.maxVolume
            self._volume_min = volume.minVolume
            self._volume = volume.volume
            self._volume_control = volume
            self._is_muted = self._volume_control.is_muted

            status = await self.dev.get_power()
            self._state = status.status
            _LOGGER.debug("Got state: %s", status)

            inputs = await self.dev.get_inputs()
            _LOGGER.debug("Got ins: %s", inputs)

            self._sources = OrderedDict()
            for input_ in inputs:
                self._sources[input_.uri] = input_
                if input_.active:
                    self._active_source = input_

            _LOGGER.debug("Active source: %s", self._active_source)

            self._available = True

            # activate notifications if wanted
            if not self._poll:
                await self.hass.async_create_task(self.async_activate_websocket())
        except SongpalException as ex:
            _LOGGER.error("Unable to update: %s", ex)
            self._available = False

    async def async_select_source(self, source):
        """Select source."""
        for out in self._sources.values():
            if out.title == source:
                await out.activate()
                return

        _LOGGER.error("Unable to find output: %s", source)

    @property
    def source_list(self):
        """Return list of available sources."""
        return [src.title for src in self._sources.values()]

    @property
    def state(self):
        """Return current state."""
        if self._state:
            return STATE_ON
        return STATE_OFF

    @property
    def source(self):
        """Return currently active source."""
        # Avoid a KeyError when _active_source is not (yet) populated
        return getattr(self._active_source, "title", None)

    @property
    def volume_level(self):
        """Return volume level."""
        volume = self._volume / self._volume_max
        return volume

    async def async_set_volume_level(self, volume):
        """Set volume level."""
        volume = int(volume * self._volume_max)
        _LOGGER.debug("Setting volume to %s", volume)
        return await self._volume_control.set_volume(volume)

    async def async_volume_up(self):
        """Set volume up."""
        return await self._volume_control.set_volume("+1")

    async def async_volume_down(self):
        """Set volume down."""
        return await self._volume_control.set_volume("-1")

    async def async_turn_on(self):
        """Turn the device on."""
        return await self.dev.set_power(True)

    async def async_turn_off(self):
        """Turn the device off."""
        return await self.dev.set_power(False)

    async def async_mute_volume(self, mute):
        """Mute or unmute the device."""
        _LOGGER.debug("Set mute: %s", mute)
        return await self._volume_control.set_mute(mute)

    @property
    def is_volume_muted(self):
        """Return whether the device is muted."""
        return self._is_muted

    @property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_SONGPAL
