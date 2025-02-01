"""The Panasonic Viera integration."""

from collections.abc import Callable
from functools import partial
import logging
from typing import Any
from urllib.error import HTTPError, URLError

from panasonic_viera import EncryptionRequired, Keys, RemoteControl, SOAPError
import voluptuous as vol

from homeassistant.components.media_player import MediaPlayerState, MediaType
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.script import Script
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_DEVICE_INFO,
    ATTR_REMOTE,
    ATTR_UDN,
    CONF_APP_ID,
    CONF_ENCRYPTION_KEY,
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
                        vol.Optional(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.REMOTE]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
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


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Panasonic Viera from a config entry."""
    panasonic_viera_data = hass.data.setdefault(DOMAIN, {})

    config = config_entry.data

    host = config[CONF_HOST]
    port = config[CONF_PORT]

    if (on_action := config[CONF_ON_ACTION]) is not None:
        on_action = Script(hass, on_action, config[CONF_NAME], DOMAIN)

    params = {}
    if CONF_APP_ID in config and CONF_ENCRYPTION_KEY in config:
        params["app_id"] = config[CONF_APP_ID]
        params["encryption_key"] = config[CONF_ENCRYPTION_KEY]

    remote = Remote(hass, host, port, on_action, **params)
    await remote.async_create_remote_control(during_setup=True)

    panasonic_viera_data[config_entry.entry_id] = {ATTR_REMOTE: remote}

    # Add device_info to older config entries
    if ATTR_DEVICE_INFO not in config or config[ATTR_DEVICE_INFO] is None:
        device_info = await remote.async_get_device_info()
        unique_id = config_entry.unique_id
        if device_info is None:
            _LOGGER.error(
                "Couldn't gather device info; Please restart Home Assistant with your"
                " TV turned on and connected to your network"
            )
        else:
            unique_id = device_info[ATTR_UDN]
        hass.config_entries.async_update_entry(
            config_entry,
            unique_id=unique_id,
            data={**config, ATTR_DEVICE_INFO: device_info},
        )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


class Remote:
    """The Remote class. It stores the TV properties and the remote control connection itself."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        on_action: Script | None = None,
        app_id: str | None = None,
        encryption_key: str | None = None,
    ) -> None:
        """Initialize the Remote class."""
        self._hass = hass

        self._host = host
        self._port = port

        self._on_action = on_action

        self._app_id = app_id
        self._encryption_key = encryption_key

        self._control: RemoteControl | None = None
        self.state: MediaPlayerState | None = None
        self.available: bool = False
        self.volume: float = 0
        self.muted: bool = False
        self.playing: bool = True

    async def async_create_remote_control(self, during_setup: bool = False) -> None:
        """Create remote control."""
        try:
            params = {}
            if self._app_id and self._encryption_key:
                params["app_id"] = self._app_id
                params["encryption_key"] = self._encryption_key

            self._control = await self._hass.async_add_executor_job(
                partial(RemoteControl, self._host, self._port, **params)
            )

            if during_setup:
                await self.async_update()
        except (URLError, SOAPError, OSError) as err:
            _LOGGER.debug("Could not establish remote connection: %s", err)
            self._control = None
            self.state = MediaPlayerState.OFF
            self.available = self._on_action is not None
        except Exception:
            _LOGGER.exception("An unknown error occurred")
            self._control = None
            self.state = MediaPlayerState.OFF
            self.available = self._on_action is not None

    async def async_update(self) -> None:
        """Update device data."""
        if self._control is None:
            await self.async_create_remote_control()
            return

        await self._handle_errors(self._update)

    def _update(self) -> None:
        """Retrieve the latest data."""
        assert self._control is not None
        self.muted = self._control.get_mute()
        self.volume = self._control.get_volume() / 100

    async def async_send_key(self, key: Keys | str) -> None:
        """Send a key to the TV and handle exceptions."""
        try:
            key = getattr(Keys, key.upper())
        except (AttributeError, TypeError):
            key = getattr(key, "value", key)

        assert self._control is not None
        await self._handle_errors(self._control.send_key, key)

    async def async_turn_on(self, context: Context | None) -> None:
        """Turn on the TV."""
        if self._on_action is not None:
            await self._on_action.async_run(context=context)
            await self.async_update()
        elif self.state is not MediaPlayerState.ON:
            await self.async_send_key(Keys.POWER)
            await self.async_update()

    async def async_turn_off(self) -> None:
        """Turn off the TV."""
        if self.state is not MediaPlayerState.OFF:
            await self.async_send_key(Keys.POWER)
            self.state = MediaPlayerState.OFF
            await self.async_update()

    async def async_set_mute(self, enable: bool) -> None:
        """Set mute based on 'enable'."""
        assert self._control is not None
        await self._handle_errors(self._control.set_mute, enable)

    async def async_set_volume(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        assert self._control is not None
        volume = int(volume * 100)
        await self._handle_errors(self._control.set_volume, volume)

    async def async_play_media(self, media_type: MediaType, media_id: str) -> None:
        """Play media."""
        assert self._control is not None
        _LOGGER.debug("Play media: %s (%s)", media_id, media_type)
        await self._handle_errors(self._control.open_webpage, media_id)

    async def async_get_device_info(self) -> dict[str, Any] | None:
        """Return device info."""
        if self._control is None:
            return None
        device_info = await self._handle_errors(self._control.get_device_info)
        _LOGGER.debug("Fetched device info: %s", str(device_info))
        return device_info

    async def _handle_errors[_R, *_Ts](
        self, func: Callable[[*_Ts], _R], *args: *_Ts
    ) -> _R | None:
        """Handle errors from func, set available and reconnect if needed."""
        try:
            result = await self._hass.async_add_executor_job(func, *args)
        except EncryptionRequired:
            _LOGGER.error(
                "The connection couldn't be encrypted. Please reconfigure your TV"
            )
            self.available = False
            return None
        except (SOAPError, HTTPError) as err:
            _LOGGER.debug("An error occurred: %s", err)
            self.state = MediaPlayerState.OFF
            self.available = True
            await self.async_create_remote_control()
            return None
        except (URLError, OSError) as err:
            _LOGGER.debug("An error occurred: %s", err)
            self.state = MediaPlayerState.OFF
            self.available = self._on_action is not None
            await self.async_create_remote_control()
            return None
        except Exception:
            _LOGGER.exception("An unknown error occurred")
            self.state = MediaPlayerState.OFF
            self.available = self._on_action is not None
            return None
        self.state = MediaPlayerState.ON
        self.available = True
        return result
