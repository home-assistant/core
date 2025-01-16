"""Config flow to configure the SFTP Backup Storage integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .client import BackupAgentError, SSHClient
from .const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD, CONF_PRIVATE_KEY_FILE, CONF_BACKUP_LOCATION, DOMAIN

def check_remote_path(client: SSHClient, path: str):
    client.sftp.chdir(path)

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
            user = user_input.get(CONF_USERNAME)
            host = user_input.get(CONF_HOST)
            port = user_input.get(CONF_PORT)

            client = SSHClient(
                host = user_input.get(CONF_HOST),
                port = user_input.get(CONF_PORT),
                username = user_input.get(CONF_USERNAME),
                password = user_input.get(CONF_PASSWORD),
                private_key_file = user_input.get(CONF_PRIVATE_KEY_FILE)
            )

            try:
                await self.hass.async_add_executor_job(
                    check_remote_path,
                    client,
                    user_input.get(CONF_BACKUP_LOCATION)
                )
            except BackupAgentError as e:
                error_message = e.args[0]
                errors["base"] = error_message
            except Exception as e:
                error_message = f'Failed attempt at checking remote directory due to exception {type(e).__name__}. {e}'
                errors["base"] = error_message
            else:
                return self.async_create_entry(title=f"SFTP Backup - {user}@{host}:{port}", data=user_input)
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema = vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=22): int,
                vol.Required(CONF_USERNAME): str,
                vol.Optional(CONF_PASSWORD): TextSelector(config=TextSelectorConfig(type=TextSelectorType.PASSWORD)),
                vol.Optional(CONF_PRIVATE_KEY_FILE): str,
                vol.Required(CONF_BACKUP_LOCATION): str,
            }),
            errors=errors,
        )