"""Config flow to configure the SFTP Backup Storage integration."""

from __future__ import annotations

from typing import Any

from asyncssh.misc import PermissionDenied
from asyncssh.sftp import SFTPNoSuchFile, SFTPPermissionDenied
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import SFTPConfigEntryData
from .client import BackupAgentClient
from .const import (
    CONF_BACKUP_LOCATION,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PRIVATE_KEY_FILE,
    CONF_USERNAME,
    DOMAIN,
    LOGGER,
)


class SFTPFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a SFTP Backup Storage config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        placeholders = {}

        if user_input is not None:
            # Create a session using your credentials
            user_config = SFTPConfigEntryData(
                host=user_input.get(CONF_HOST),
                port=user_input.get(CONF_PORT),
                username=user_input.get(CONF_USERNAME),
                password=user_input.get(CONF_PASSWORD),
                private_key_file=user_input.get(CONF_PRIVATE_KEY_FILE),
                backup_location=user_input.get(CONF_BACKUP_LOCATION),
            )

            placeholders["backup_location"] = user_config.backup_location

            try:
                # Raises:
                # - OSError, if host or port are not correct.
                # - asyncssh.misc.PermissionDenied, if credentials are not correct.
                # - asyncssh.sftp.SFTPNoSuchFile, if directory does not exist.
                # - asyncssh.sftp.SFTPPermissionDenied, if we don't have access to said directory
                async with BackupAgentClient(user_config) as client:
                    await client.list_backup_location()
                    identifier = client.get_identifier()
                    LOGGER.debug(
                        "Will register SFTP Backup Location agent with identifier %s",
                        identifier,
                    )

            except OSError as e:
                placeholders["error_message"] = str(e)
                errors["base"] = "os_error"
            except PermissionDenied as e:
                placeholders["error_message"] = str(e)
                errors["base"] = "permission_denied"
            except SFTPNoSuchFile:
                errors["base"] = "sftp_no_such_file"
            except SFTPPermissionDenied:
                errors["base"] = "sftp_permission_denied"
            except ConfigEntryError as e:
                placeholders["error_message"] = str(e)
                errors["base"] = "config_entry_error"
            except Exception as e:  # noqa: BLE001
                LOGGER.exception(e)
                placeholders["error_message"] = str(e)
                placeholders["exception"] = type(e).__name__
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(identifier)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"SFTP Backup - {user_config.username}@{user_config.host}:{user_config.port}",
                    data=user_input,
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
            description_placeholders=placeholders,
            errors=errors,
        )
