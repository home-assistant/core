"""The Panasonic Viera integration."""
import asyncio
from datetime import timedelta
from functools import partial
import logging
from urllib.request import URLError

from panasonic_viera import EncryptionRequired, Keys, RemoteControl, SOAPError
import voluptuous as vol

from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.script import Script

from .const import (
    ATTR_REMOTE,
    CONF_APP_ID,
    CONF_ENCRYPTION_KEY,
    CONF_LISTEN_PORT,
    CONF_ON_ACTION,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): cv.string,
                        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                        vol.Optional(CONF_LISTEN_PORT, default=DEFAULT_PORT): cv.port,
                        vol.Optional(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [MEDIA_PLAYER_DOMAIN, REMOTE_DOMAIN]

URL_EVENT_0_DMR = "dmr/event_0"
URL_EVENT_0_NRC = "nrc/event_0"

UPNP_SERVICES = [URL_EVENT_0_DMR, URL_EVENT_0_NRC]

MAP_APP_NAME = {"platinum": "Browser", "Amazon": "Prime Video"}

RESUBSCRIBE_INTERVAL = timedelta(seconds=90)


async def async_setup(hass, config):
    """Set up Panasonic Viera from configuration.yaml."""
    if DOMAIN not in config:
        return True

    for conf in config[DOMAIN]:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
            )
        )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up Panasonic Viera from a config entry."""

    panasonic_viera_data = hass.data.setdefault(DOMAIN, {})

    config = config_entry.data

    host = config[CONF_HOST]
    port = config[CONF_PORT]

    if CONF_LISTEN_PORT not in config:
        config_entry = hass.config_entries.async_update_entry(
            config_entry, data={**config, CONF_LISTEN_PORT: DEFAULT_PORT},
        )
        config = config_entry.data

    listen_port = config[CONF_LISTEN_PORT]

    on_action = config[CONF_ON_ACTION]
    if on_action is not None:
        on_action = Script(hass, on_action)

    params = {}
    if CONF_APP_ID in config and CONF_ENCRYPTION_KEY in config:
        params["app_id"] = config[CONF_APP_ID]
        params["encryption_key"] = config[CONF_ENCRYPTION_KEY]

    remote = Remote(hass, host, port, listen_port, on_action, **params)
    await remote.async_create_remote_control(during_setup=True)

    panasonic_viera_data[config_entry.entry_id] = {ATTR_REMOTE: remote}

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, remote.shutdown)
    async_track_time_interval(hass, remote.resubscribe_all, RESUBSCRIBE_INTERVAL)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


class Remote:
    """The Remote class. It stores the TV properties and the remote control connection itself."""

    def __init__(
        self,
        hass,
        host,
        port,
        listen_port=DEFAULT_PORT,
        on_action=None,
        app_id=None,
        encryption_key=None,
    ):
        """Initialize the Remote class."""
        self._hass = hass

        self._host = host
        self._port = port

        self._listen_port = listen_port

        self._on_action = on_action

        self._app_id = app_id
        self._encryption_key = encryption_key

        self.available = False
        self.connected = False

        self._state = STATE_OFF
        self._app_info = None
        self._volume = "0"
        self._mute = "0"

        self.playing = False

        self._control = None

    async def async_create_remote_control(self, during_setup=False):
        """Create remote control."""
        try:
            params = {}
            if self._app_id and self._encryption_key:
                params["app_id"] = self._app_id
                params["encryption_key"] = self._encryption_key

            control = await self._hass.async_add_executor_job(
                partial(
                    RemoteControl,
                    self._host,
                    self._port,
                    listen_port=self._listen_port,
                    **params,
                )
            )

            await control.async_start_server()
            control.on_event = self.on_event

            for service in UPNP_SERVICES:
                await self._hass.async_add_executor_job(
                    partial(control.upnp_service_subscribe, service)
                )

            self._control = control

            self.available = True
            self.connected = True
        except (TimeoutError, URLError, SOAPError, OSError) as err:
            if during_setup:
                _LOGGER.debug("Could not establish remote connection: %s", err)

            self.available = self._on_action is not None
            self.connected = False
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception("An unknown error occurred: %s", err)
            self.available = self._on_action is not None
            self.connected = False

    async def async_update(self):
        """Update device data or try reconnectiion."""
        if not self.connected:
            await self.async_create_remote_control()
            return

        await self._handle_errors(self._update)

    def _update(self):
        """Update device data."""
        self._volume = self._control.get_volume()
        self._mute = self._control.get_mute()

        self.available = True
        self.connected = True

    def resubscribe_all(self):
        """Resubscribe to all services."""
        if self._control is not None:
            for service in UPNP_SERVICES:
                try:
                    self._control.upnp_service_unsubscribe(service)
                    self._control.upnp_service_subscribe(service)
                except (TimeoutError, URLError, OSError):
                    _LOGGER.debug("Could resubscribe to service %s", service)

    async def async_send_key(self, key):
        """Send a key to the TV and handle exceptions."""
        try:
            key = getattr(Keys, key)
        except (AttributeError, TypeError):
            key = getattr(key, "value", key)

        await self._handle_errors(self._control.send_key, key)

    async def async_turn_on(self):
        """Turn on the TV."""
        if self._on_action is not None:
            await self._on_action.async_run()
        elif self.state != STATE_ON:
            await self.async_send_key(Keys.power)

    async def async_turn_off(self):
        """Turn off the TV."""
        if self.state != STATE_OFF:
            await self.async_send_key(Keys.power)
            await self.async_update()

    async def async_set_mute(self, enable):
        """Set mute based on 'enable'."""
        await self._handle_errors(self._control.set_mute, enable)

    async def async_set_volume(self, volume):
        """Set volume level, range 0..1."""
        volume = int(volume * 100)
        await self._handle_errors(self._control.set_volume, volume)

    async def async_play_media(self, media_type, media_id):
        """Open webpage."""
        _LOGGER.debug("Play media: %s (%s)", media_id, media_type)
        await self._handle_errors(self._control.open_webpage, media_id)

    async def _handle_errors(self, func, *args):
        """Handle errors from func, set available and reconnect if needed."""
        try:
            return await self._hass.async_add_executor_job(func, *args)
        except EncryptionRequired:
            _LOGGER.error(
                "The connection couldn't be encrypted. Please reconfigure your TV"
            )
        except (TimeoutError, URLError, SOAPError, OSError) as err:
            _LOGGER.debug("Could not establish remote connection: %s", err)
            if self._control is not None:
                await self.shutdown()
            self.available = self._on_action is not None
            self.connected = False
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception("An unknown error occurred: %s", err)
            if self._control is not None:
                await self.shutdown()
            self.available = self._on_action is not None
            self.connected = False

    async def on_event(self, service, properties):
        """Parse and store received properties."""
        if service is URL_EVENT_0_DMR:
            if "Volume" in properties:
                self._volume = properties["Volume"]["@val"]
            if "Mute" in properties:
                self._mute = properties["Mute"]["@val"]
            return

        if service is URL_EVENT_0_NRC:
            if "X_ScreenState" in properties:
                self._state = properties["X_ScreenState"]
                return
            if "X_AppInfo" in properties:
                self._app_info = properties["X_AppInfo"]
                return

            self._state = properties[2]["X_ScreenState"]
            self._app_info = properties[3]["X_AppInfo"]

    async def shutdown(self, *args):
        """Stop HTTP server and unsubscribe from UPnP services."""
        if self._control is not None:
            try:
                await self._control.async_stop_server()
            except OSError:
                _LOGGER.debug("Could not stop HTTP server")
            for service in UPNP_SERVICES:
                try:
                    return await self._hass.async_add_executor_job(
                        partial(self._control.upnp_service_unsubscribe, service)
                    )
                except (TimeoutError, URLError, OSError):
                    _LOGGER.debug("Could not unsubscribe from service %s", service)

    @property
    def state(self):
        """Return TV state."""
        return self._state

    @property
    def app_name(self):
        """Return name of open app."""
        if self._app_info is not None:
            app_name = self._app_info.split(":")[3]
            if app_name == "null":
                return None
            if app_name in MAP_APP_NAME:
                return MAP_APP_NAME[app_name]
            return app_name
        return None

    @property
    def app_id(self):
        """Return ID of open app."""
        if self._app_info is not None:
            return self._app_info.split(":")[2].split("=")[1]
        return None

    @property
    def volume(self):
        """Return current volume level."""
        return int(self._volume) / 100

    @property
    def muted(self):
        """Return if TV is muted."""
        return self._mute == "1"
