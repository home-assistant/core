"""Config flow to configure the SFTP Backup Storage integration."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from asyncssh import SSHClientConnectionOptions, connect
from asyncssh.misc import PermissionDenied
from asyncssh.sftp import SFTPNoSuchFile, SFTPPermissionDenied
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import slugify

from . import SFTPConfigEntryData
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
    """Handle an SFTP Backup Storage config flow."""

    def _check_pkey_and_password(self, user_input: dict) -> dict:
        """Check if user provided either one of password or private key.

        Additionally, check if private key exists and make sure it starts
        with `/config` if full path is not provided by user.

        Returns: user_input object with edited private key location, if edited.
        """
        # If both password AND private key are not provided, error out.
        # We need at least one to perform authentication.
        if (
            bool(user_input.get(CONF_PASSWORD)) is False
            and bool(user_input.get(CONF_PRIVATE_KEY_FILE)) is False
        ):
            raise ConfigEntryError(
                "Please configure password or private key file location for SFTP Backup Storage."
            )

        if bool(user_input.get(CONF_PRIVATE_KEY_FILE)):
            # If full path to private key is not provided,
            # fallback to /config as a main directory to look for pkey.
            if not user_input[CONF_PRIVATE_KEY_FILE].startswith("/"):
                user_input[CONF_PRIVATE_KEY_FILE] = (
                    "/config/" + user_input[CONF_PRIVATE_KEY_FILE]
                )

            # Error out if we did not find the private key file.
            if not Path(user_input[CONF_PRIVATE_KEY_FILE]).exists():
                raise ConfigEntryError(
                    f"Private key file not found in provided path: `{user_input[CONF_PRIVATE_KEY_FILE]}`."
                    " Place the key file in config or share directory "
                    "and point to it by specifying path "
                    "`/config/private_key` or `/share/private_key`.",
                )

        return user_input

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon connection failure."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        return await self.async_step_user(user_input, "reauth_confirm")

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
        step_id="user",
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}

        if user_input is not None:
            LOGGER.debug("Source: ", self.source)

            # Create a session using your credentials
            user_config = SFTPConfigEntryData(
                host=user_input[CONF_HOST],
                port=user_input.get(CONF_PORT, 22),
                username=user_input[CONF_USERNAME],
                password=user_input.get(CONF_PASSWORD),
                private_key_file=user_input.get(CONF_PRIVATE_KEY_FILE),
                backup_location=user_input[CONF_BACKUP_LOCATION],
            )

            placeholders["backup_location"] = user_config.backup_location

            try:
                # Performs a username-password entry check
                # Validates private key location if provided.
                user_input = self._check_pkey_and_password(user_input)

                # Raises:
                # - OSError, if host or port are not correct.
                # - asyncssh.misc.PermissionDenied, if credentials are not correct.
                # - asyncssh.sftp.SFTPNoSuchFile, if directory does not exist.
                # - asyncssh.sftp.SFTPPermissionDenied, if we don't have access to said directory
                async with (
                    connect(
                        host=user_config.host,
                        port=user_config.port,
                        options=SSHClientConnectionOptions(
                            known_hosts=None,
                            username=user_config.username,
                            password=user_config.password,
                            client_keys=[user_config.private_key_file]
                            if user_config.private_key_file
                            else None,
                        ),
                    ) as ssh,
                    ssh.start_sftp_client() as sftp,
                ):
                    await sftp.chdir(user_config.backup_location)
                    await sftp.listdir()

                identifier = slugify(
                    ".".join(
                        [
                            user_config.host,
                            str(user_config.port),
                            user_config.username,
                            user_config.backup_location,
                        ]
                    )
                )
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
                LOGGER.error("Placeholders: %s", placeholders)
                LOGGER.error("Base: %s", errors)
            except Exception as e:  # noqa: BLE001
                LOGGER.exception(e)
                placeholders["error_message"] = str(e)
                placeholders["exception"] = type(e).__name__
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(identifier)

                if self.source == SOURCE_REAUTH:
                    reauth_entry = self._get_reauth_entry()
                    self._abort_if_unique_id_mismatch(
                        reason="reauth_key_changes",
                    )
                    return self.async_update_reload_and_abort(
                        reauth_entry, data=user_input
                    )

                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"{user_config.username}@{user_config.host}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id=step_id,
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
