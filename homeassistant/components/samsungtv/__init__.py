"""The Samsung TV integration."""
import socket
import time
from typing import Iterable, Optional

import samsungctl
import voluptuous as vol
import websocket

from homeassistant.components.media_player.const import DOMAIN as MP_DOMAIN
from homeassistant.components.remote import DEFAULT_DELAY_SECS, DOMAIN as REMOTE_DOMAIN
from homeassistant.const import CONF_HOST, CONF_METHOD, CONF_NAME, CONF_PORT
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

from .const import (
    COMMAND_RETRY_COUNT,
    CONF_ON_ACTION,
    DEFAULT_NAME,
    DOMAIN,
    KEY_REMOTE,
    LOGGER,
)


def ensure_unique_hosts(value):
    """Validate that all configs have a unique host."""
    vol.Schema(vol.Unique("duplicate host entries found"))(
        [socket.gethostbyname(entry[CONF_HOST]) for entry in value]
    )
    return value


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): cv.string,
                        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                        vol.Optional(CONF_PORT): cv.port,
                        vol.Optional(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
                    }
                )
            ],
            ensure_unique_hosts,
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Samsung TV integration."""
    if DOMAIN in config:
        hass.data[DOMAIN] = {}
        for entry_config in config[DOMAIN]:
            ip_address = await hass.async_add_executor_job(
                socket.gethostbyname, entry_config[CONF_HOST]
            )
            hass.data[DOMAIN][ip_address] = {
                CONF_ON_ACTION: entry_config.get(CONF_ON_ACTION)
            }
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": "import"}, data=entry_config
                )
            )

    return True


async def async_setup_entry(hass, entry):
    """Set up the Samsung TV platform."""
    data = hass.data.setdefault(DOMAIN, {})
    data.setdefault(entry.entry_id, {})[KEY_REMOTE] = RemoteWrapper(hass, entry)

    await discovery.async_load_platform(
        hass, REMOTE_DOMAIN, DOMAIN, entry, hass.config.as_dict(),
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, MP_DOMAIN)
    )

    return True


class RemoteWrapper:
    """Remote control helper for Samsung TV platforms."""

    def __init__(self, hass, config_entry):
        """Initialize remote control helper."""
        self.hass = hass
        self._last_command_sent = time.monotonic() - DEFAULT_DELAY_SECS
        self._remote: Optional[samsungctl.Remote] = None
        # Configuration for the Samsung library
        self._config = {
            "name": "HomeAssistant",
            "description": "HomeAssistant",
            "id": "ha.component.samsung",
            "method": config_entry.data[CONF_METHOD],
            "port": config_entry.data.get(CONF_PORT),
            "host": config_entry.data[CONF_HOST],
            "timeout": 1,
        }

    def get_remote(self, force_reconnect: bool = False) -> samsungctl.Remote:
        """Create or return a remote control instance."""
        if self._remote is not None:
            if force_reconnect:
                self.close()
            else:
                return self._remote

        # Create a new instance to reconnect
        try:
            self._remote = samsungctl.Remote(self._config.copy())
        except samsungctl.exceptions.AccessDenied:
            # This is only happening when the auth was switched to DENY.
            # A removed auth will lead to socket timeout because waiting for
            # auth popup is just an open socket.
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": "reauth"}, data=self._config_entry.data,
                )
            )
            raise

        return self._remote

    def reconnect(self) -> bool:
        """Reconnect the remote control."""
        try:
            _ = self.get_remote(force_reconnect=True)
        except (
            samsungctl.exceptions.UnhandledResponse,
            samsungctl.exceptions.AccessDenied,
        ):
            # We got a response so it's working
            return True
        except (OSError, websocket.WebSocketException):
            return False
        else:
            return True

    def close(self) -> None:
        """Close remote connection."""
        if self._remote is not None:
            self._remote.close()
            self._remote = None

    def send_commands(self, commands: Iterable[str], delay: float = 0) -> None:
        """Send commands to TV."""
        for command in commands:
            self.send_command(command, delay)

    def send_command(self, command: str, delay: float = 0) -> None:
        """Send a command to TV."""
        # Wait remaining delay
        time.sleep(max(0, self._last_command_sent + delay - time.monotonic()))
        try:
            # Recreate connection if it was dead
            for _ in range(COMMAND_RETRY_COUNT):
                try:
                    self.get_remote().control(command)
                    break
                except (
                    samsungctl.exceptions.ConnectionClosed,
                    BrokenPipeError,
                    websocket.WebSocketException,
                ):
                    # BrokenPipe can occur when the commands are sent too fast,
                    # WebSocketException can occur when timed out.
                    self._remote = None
        except (
            samsungctl.exceptions.UnhandledResponse,
            samsungctl.exceptions.AccessDenied,
        ):
            # We got a response so the TV is on.
            LOGGER.debug("Failed sending command %s", command, exc_info=True)
        except OSError:
            # Different reasons, e.g. hostname not resolveable.
            pass
        self._last_command_sent = time.monotonic()
