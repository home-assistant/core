"""Config flow to configure the SFTP Backup Storage integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .client import SSHClient
from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_PRIVATE_KEY_FILE,
    CONF_BACKUP_LOCATION,
    DOMAIN,
    LOGGER,
)


def check_remote_path(client: SSHClient, path: str) -> None:
    """Changes directory to given path. Raises exception if the requested path doesn't exist on the server"""
    sftp = client.open_sftp()
    sftp.chdir(path)


class SFTPFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a SFTP Backup Storage config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            # Create a session using your credentials
            host: str = user_input.get(CONF_HOST)
            port: int = user_input.get(CONF_PORT)
            user: str = user_input.get(CONF_USERNAME)
            private_key_file: str = user_input.get(CONF_PRIVATE_KEY_FILE)
            backup_location: str = user_input.get(CONF_BACKUP_LOCATION)

            # If full path is not provided to private_key_file,
            # default to look at /config directory
            if private_key_file and not private_key_file.startswith("/"):
                private_key_file = f"/config/{private_key_file}"

            try:
                client = SSHClient(
                    host=host,
                    port=port,
                    username=user,
                    password=user_input.get(CONF_PASSWORD),
                    private_key_file=private_key_file,
                    backup_location=backup_location,
                )

                await self.hass.async_add_executor_job(
                    check_remote_path, client, backup_location
                )
            except FileNotFoundError as e:
                errors["base"] = (
                    f"Remote path not found. Please check if path: '{backup_location}' exists remotely."
                )
            except ConfigEntryError as e:
                errors["base"] = str(e)
            except Exception as e:
                LOGGER.exception(e)
                errors["base"] = (
                    f"Unexpected exception ({type(e).__name__}) occurred during config flow. {e}"
                )
            else:
                identifier = client.get_identifier()
                await self.async_set_unique_id(identifier)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"SFTP Backup - {user}@{host}:{port}", data=user_input
                )
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=22): int,
                    vol.Required(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): TextSelector(
                        config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                    vol.Optional(CONF_PRIVATE_KEY_FILE): str,
                    vol.Required(CONF_BACKUP_LOCATION): str,
                }
            ),
            errors=errors,
        )
