"""Config flow to configure the SFTP Storage integration."""

from __future__ import annotations

from typing import Any, cast

from asyncssh import connect
from asyncssh.misc import PermissionDenied
from asyncssh.sftp import SFTPNoSuchFile, SFTPPermissionDenied
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    FileSelector,
    FileSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import SFTPConfigEntryData
from .client import get_client_options, save_uploaded_pkey_file
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
from .exceptions import SFTPStorageInvalidPrivateKey, SFTPStorageMissingPasswordOrPkey


class SFTPFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle an SFTP Storage config flow."""

    def __init__(self) -> None:
        """Initialize SFTP Storage Flow Handler.

        Initialize _client_keys as an instance variable to ensure each config flow
        handler instance has its own isolated list of SSH client keys. This prevents
        key files from previous config flow attempts (especially in tests) from
        persisting.
        """
        self._client_keys: list = []

    async def _check_pkey_and_password(
        self, user_input: dict[str, Any]
    ) -> dict[str, Any]:
        """Check if user provided either one of password or private key.

        Additionally, check if private key exists and make sure it starts
        with `/config` if full path is not provided by user.

        Returns: user_input object with edited private key location, if edited.

        Raises:
            - SFTPStorageMissingPasswordOrPkey - If user did not provide password nor private key.
            - SFTPStorageInvalidPrivateKey - If private key is not valid format.
        """
        # If both password AND private key are not provided, error out.
        # We need at least one to perform authentication.
        if (
            bool(user_input.get(CONF_PASSWORD)) is False
            and bool(user_input.get(CONF_PRIVATE_KEY_FILE)) is False
        ):
            raise SFTPStorageMissingPasswordOrPkey

        if bool(user_input.get(CONF_PRIVATE_KEY_FILE)):
            self._client_keys.append(
                # This will raise SFTPStorageInvalidPrivateKey if private key is invalid.
                await save_uploaded_pkey_file(
                    self.hass, cast(str, user_input.get(CONF_PRIVATE_KEY_FILE))
                )
            )

        return user_input

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
        step_id: str = "user",
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}

        if user_input is not None:
            LOGGER.debug("Source: %s", self.source)

            # Create a session using your credentials
            user_config = SFTPConfigEntryData(
                host=user_input[CONF_HOST],
                port=user_input.get(CONF_PORT, 22),
                username=user_input[CONF_USERNAME],
                password=user_input.get(CONF_PASSWORD),
                private_key_file=self._client_keys,
                backup_location=user_input[CONF_BACKUP_LOCATION],
            )

            placeholders["backup_location"] = user_config.backup_location

            try:
                # Performs a username-password entry check
                # Validates private key location if provided.
                user_input = await self._check_pkey_and_password(user_input)

                # Raises:
                # - OSError, if host or port are not correct.
                # - SFTPStorageInvalidPrivateKey, if private key is not valid format.
                # - asyncssh.misc.PermissionDenied, if credentials are not correct.
                # - SFTPStorageMissingPasswordOrPkey, if password and private key are not provided.
                # - asyncssh.sftp.SFTPNoSuchFile, if directory does not exist.
                # - asyncssh.sftp.SFTPPermissionDenied, if we don't have access to said directory
                async with (
                    connect(
                        host=user_config.host,
                        port=user_config.port,
                        options=await self.hass.async_add_executor_job(
                            get_client_options, user_config
                        ),
                    ) as ssh,
                    ssh.start_sftp_client() as sftp,
                ):
                    await sftp.chdir(user_config.backup_location)
                    await sftp.listdir()

                LOGGER.debug(
                    "Will register SFTP Storage agent with identifier %s",
                    user_config.unique_id,
                )

            except OSError as e:
                LOGGER.exception(e)
                placeholders["error_message"] = str(e)
                errors["base"] = "os_error"
            except SFTPStorageInvalidPrivateKey:
                errors["base"] = "invalid_key"
            except PermissionDenied as e:
                placeholders["error_message"] = str(e)
                errors["base"] = "permission_denied"
            except SFTPStorageMissingPasswordOrPkey:
                errors["base"] = "key_or_password_needed"
            except SFTPNoSuchFile:
                errors["base"] = "sftp_no_such_file"
            except SFTPPermissionDenied:
                errors["base"] = "sftp_permission_denied"
            except Exception as e:  # noqa: BLE001
                LOGGER.exception(e)
                placeholders["error_message"] = str(e)
                placeholders["exception"] = type(e).__name__
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_config.unique_id)
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
                    vol.Optional(CONF_PRIVATE_KEY_FILE): FileSelector(
                        FileSelectorConfig(accept="*")
                    ),
                    vol.Required(CONF_BACKUP_LOCATION): str,
                }
            ),
            description_placeholders=placeholders,
            errors=errors,
        )
