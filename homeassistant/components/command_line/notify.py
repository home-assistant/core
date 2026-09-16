"""Support for command line notification services."""

import asyncio
from contextlib import suppress
from typing import Any, override

from homeassistant.components.notify import (
    DOMAIN as NOTIFY_DOMAIN,
    BaseNotificationService,
)
from homeassistant.const import CONF_COMMAND
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_COMMAND_TIMEOUT, DOMAIN, LOGGER
from .utils import create_platform_yaml_not_supported_issue, render_template_args


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> CommandLineNotificationService | None:
    """Get the Command Line notification service."""
    if not discovery_info:
        create_platform_yaml_not_supported_issue(hass, NOTIFY_DOMAIN)
        return None

    notify_config = discovery_info
    command: str = notify_config[CONF_COMMAND]
    timeout: int = notify_config[CONF_COMMAND_TIMEOUT]

    return CommandLineNotificationService(command, timeout)


class CommandLineNotificationService(BaseNotificationService):
    """Implement the notification service for the Command Line service."""

    def __init__(self, command: str, timeout: int) -> None:
        """Initialize the service."""
        self.command = command
        self._timeout = timeout

    @override
    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a command line."""
        if not (command := render_template_args(self.hass, self.command)):
            return

        LOGGER.debug("Running with message: %s", message)

        try:
            proc = await asyncio.create_subprocess_shell(  # shell by design
                command,
                stdin=asyncio.subprocess.PIPE,
                close_fds=False,  # required for posix_spawn
            )
        except OSError as err:
            LOGGER.debug("Error trying to exec command: %s", command)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_error",
                translation_placeholders={"command": command, "error": str(err)},
            ) from err

        try:
            async with asyncio.timeout(self._timeout):
                await proc.communicate(input=message.encode())
        except TimeoutError as err:
            LOGGER.debug("Timeout for command: %s", command)
            with suppress(ProcessLookupError):
                # The command may have exited between the timeout and the kill.
                proc.kill()
            if (stdin := proc.stdin) is not None and (
                not stdin.is_closing() or stdin.transport.get_write_buffer_size()
            ):
                # A still connected stdin pipe keeps proc.wait() pending forever,
                # see https://bugs.python.org/issue43884.
                stdin.transport.abort()
            await proc.wait()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="timeout_error",
                translation_placeholders={"command": command},
            ) from err
        except asyncio.CancelledError:
            # Kill synchronously so the child isn't orphaned; the event loop
            # reaps it without awaiting wait(), which cancellation would
            # interrupt anyway.
            with suppress(ProcessLookupError):
                proc.kill()
            raise

        if proc.returncode != 0:
            LOGGER.error(
                "Command failed (with return code %s): %s",
                proc.returncode,
                command,
            )
