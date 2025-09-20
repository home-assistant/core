"""Config flow to configure the SFTP Storage integration."""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path
import shutil
from typing import Any, cast

from asyncssh import KeyImportError, SSHClientConnectionOptions, connect
from asyncssh.misc import PermissionDenied
from asyncssh.sftp import SFTPNoSuchFile, SFTPPermissionDenied
import voluptuous as vol

from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    FileSelector,
    FileSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.util.ulid import ulid

from . import SFTPConfigEntryData
from .client import get_client_options
from .const import (
    CONF_BACKUP_LOCATION,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PRIVATE_KEY_FILE,
    CONF_USERNAME,
    DEFAULT_PKEY_NAME,
    DOMAIN,
    LOGGER,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=22): int,
        vol.Required(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): TextSelector(
            config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Optional(CONF_PRIVATE_KEY_FILE): FileSelector(
            FileSelectorConfig(accept="*")
        ),
        vol.Required(CONF_BACKUP_LOCATION): str,
    }
)


class SFTPStorageException(Exception):
    """Base exception for SFTP Storage integration."""


class SFTPStorageInvalidPrivateKey(SFTPStorageException):
    """Exception raised during config flow - when user provided invalid private key file."""


class SFTPStorageMissingPasswordOrPkey(SFTPStorageException):
    """Exception raised during config flow - when user did not provide password or private key file."""


class SFTPFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle an SFTP Storage config flow."""

    def __init__(self) -> None:
        """Initialize SFTP Storage Flow Handler."""
        self._client_keys: list = []

    async def _validate_auth_and_save_keyfile(
        self, user_input: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate authentication input and persist uploaded key file.

        Ensures that at least one of password or private key is provided. When a
        private key is supplied, the uploaded file is saved to Home Assistant's
        config storage and `user_input[CONF_PRIVATE_KEY_FILE]` is replaced with
        the stored path.

        Returns: the possibly updated `user_input`.

        Raises:
            - SFTPStorageMissingPasswordOrPkey: Neither password nor private key provided
            - SFTPStorageInvalidPrivateKey: The provided private key has an invalid format
        """

        # If neither password nor private key is provided, error out;
        # we need at least one to perform authentication.
        if not (user_input.get(CONF_PASSWORD) or user_input.get(CONF_PRIVATE_KEY_FILE)):
            raise SFTPStorageMissingPasswordOrPkey

        if key_file := user_input.get(CONF_PRIVATE_KEY_FILE):
            client_key = await save_uploaded_pkey_file(self.hass, cast(str, key_file))

            LOGGER.debug("Saved client key: %s", client_key)
            user_input[CONF_PRIVATE_KEY_FILE] = client_key

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

            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_BACKUP_LOCATION: user_input[CONF_BACKUP_LOCATION],
                }
            )

            try:
                # Validate auth input and save uploaded key file if provided
                user_input = await self._validate_auth_and_save_keyfile(user_input)

                # Create a session using your credentials
                user_config = SFTPConfigEntryData(
                    host=user_input[CONF_HOST],
                    port=user_input[CONF_PORT],
                    username=user_input[CONF_USERNAME],
                    password=user_input.get(CONF_PASSWORD),
                    private_key_file=user_input.get(CONF_PRIVATE_KEY_FILE),
                    backup_location=user_input[CONF_BACKUP_LOCATION],
                )

                placeholders["backup_location"] = user_config.backup_location

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
                    "Will register SFTP Storage agent with user@host %s@%s",
                    user_config.host,
                    user_config.username,
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
                return self.async_create_entry(
                    title=f"{user_config.username}@{user_config.host}",
                    data=user_input,
                )
            finally:
                # We remove the saved private key file if any error occurred.
                if errors and bool(user_input.get(CONF_PRIVATE_KEY_FILE)):
                    keyfile = Path(user_input[CONF_PRIVATE_KEY_FILE])
                    keyfile.unlink(missing_ok=True)
                    with suppress(OSError):
                        keyfile.parent.rmdir()

        if user_input:
            user_input.pop(CONF_PRIVATE_KEY_FILE, None)

        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(DATA_SCHEMA, user_input),
            description_placeholders=placeholders,
            errors=errors,
        )


async def save_uploaded_pkey_file(hass: HomeAssistant, uploaded_file_id: str) -> str:
    """Validate the uploaded private key and move it to the storage directory.

    Return a string representing a path to private key file.
    Raises SFTPStorageInvalidPrivateKey if the file is invalid.
    """

    def _process_upload() -> str:
        with process_uploaded_file(hass, uploaded_file_id) as file_path:
            try:
                # Initializing this will verify if private key is in correct format
                SSHClientConnectionOptions(client_keys=[file_path])
            except KeyImportError as err:
                LOGGER.debug(err)
                raise SFTPStorageInvalidPrivateKey from err

            dest_path = Path(hass.config.path(STORAGE_DIR, DOMAIN))
            dest_file = dest_path / f".{ulid()}_{DEFAULT_PKEY_NAME}"

            # Create parent directory
            dest_file.parent.mkdir(exist_ok=True)
            return str(shutil.move(file_path, dest_file))

    return await hass.async_add_executor_job(_process_upload)
