"""Config flow to configure the iCloud integration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import logging
import os
from typing import TYPE_CHECKING, Any

from pyicloud import PyiCloudService
from pyicloud.exceptions import (
    PyiCloudException,
    PyiCloudFailedLoginException,
    PyiCloudNoDevicesException,
    PyiCloudServiceNotActivatedException,
)
from pyicloud.services.photos import AlbumContainer, BasePhotoAlbum
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import progress_step
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.storage import Store

from .const import (
    CONF_ALBUM_ID,
    CONF_ALBUM_NAME,
    CONF_ALBUM_TYPE,
    CONF_GPS_ACCURACY_THRESHOLD,
    CONF_MAX_INTERVAL,
    CONF_PICTURE_INTERVAL,
    CONF_RANDOM_ORDER,
    CONF_WITH_FAMILY,
    DEFAULT_GPS_ACCURACY_THRESHOLD,
    DEFAULT_MAX_INTERVAL,
    DEFAULT_PICTURE_INTERVAL,
    DEFAULT_RANDOM_ORDER,
    DEFAULT_WITH_FAMILY,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)

CONF_TRUSTED_DEVICE = "trusted_device"
CONF_VERIFICATION_CODE = "verification_code"

_LOGGER = logging.getLogger(__name__)


class IcloudFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a iCloud config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize iCloud config flow."""
        self.api: PyiCloudService | None = None
        self._username: str = ""
        self._password: str = ""
        self._with_family: bool = DEFAULT_WITH_FAMILY
        self._max_interval: int = DEFAULT_MAX_INTERVAL
        self._gps_accuracy_threshold: int = DEFAULT_GPS_ACCURACY_THRESHOLD

        self._trusted_device: dict[str, Any] | None = None
        self._existing_entry_data: dict[str, Any] | None = None
        self._description_placeholders: dict[str, str] | None = None

    def _show_setup_form(
        self, user_input=None, errors=None, step_id="user"
    ) -> ConfigFlowResult:
        """Show the setup form to the user."""

        if user_input is None:
            user_input = {}

        if step_id == "user":
            schema = {
                vol.Required(
                    CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                ): str,
                vol.Required(
                    CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                ): str,
                vol.Optional(
                    CONF_WITH_FAMILY,
                    default=user_input.get(CONF_WITH_FAMILY, DEFAULT_WITH_FAMILY),
                ): bool,
            }
        else:
            schema = {
                vol.Required(
                    CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                ): str,
            }

        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(schema),
            errors=errors or {},
            description_placeholders=self._description_placeholders,
        )

    async def _validate_and_create_entry(
        self, user_input: dict[str, Any], step_id: str
    ) -> ConfigFlowResult:
        """Check if config is valid and create entry if so."""
        self._password = user_input[CONF_PASSWORD]

        extra_inputs: dict[str, Any] = user_input

        # If an existing entry was found, meaning this is a password update attempt,
        # use those to get config values that aren't changing
        if self._existing_entry_data:
            extra_inputs = self._existing_entry_data

        self._username = extra_inputs[CONF_USERNAME]
        self._with_family = extra_inputs.get(CONF_WITH_FAMILY, DEFAULT_WITH_FAMILY)
        self._max_interval = extra_inputs.get(CONF_MAX_INTERVAL, DEFAULT_MAX_INTERVAL)
        self._gps_accuracy_threshold = extra_inputs.get(
            CONF_GPS_ACCURACY_THRESHOLD, DEFAULT_GPS_ACCURACY_THRESHOLD
        )

        # Check if already configured
        if self.unique_id is None:
            await self.async_set_unique_id(self._username)
            self._abort_if_unique_id_configured()

        try:
            self.api = await self.hass.async_add_executor_job(
                PyiCloudService,
                self._username,
                self._password,
                Store(self.hass, STORAGE_VERSION, STORAGE_KEY).path,
                True,
                None,
                self._with_family,
            )
        except PyiCloudFailedLoginException as error:
            _LOGGER.error("Error logging into iCloud service: %s", error)
            self.api = None
            errors: dict[str, str] = {CONF_PASSWORD: "invalid_auth"}
            return self._show_setup_form(user_input, errors, step_id)

        if TYPE_CHECKING:
            assert self.api is not None

        if self.api.requires_2fa:
            return await self.async_step_verification_code()

        if self.api.requires_2sa:
            return await self.async_step_trusted_device()

        try:
            devices = await self.hass.async_add_executor_job(
                getattr, self.api, "devices"
            )
            if not devices:
                raise PyiCloudNoDevicesException  # noqa: TRY301
        except (PyiCloudServiceNotActivatedException, PyiCloudNoDevicesException):
            _LOGGER.error("No device found in the iCloud account: %s", self._username)
            self.api = None
            return self.async_abort(reason="no_device")

        data = {
            CONF_USERNAME: self._username,
            CONF_PASSWORD: self._password,
            CONF_WITH_FAMILY: self._with_family,
            CONF_MAX_INTERVAL: self._max_interval,
            CONF_GPS_ACCURACY_THRESHOLD: self._gps_accuracy_threshold,
        }

        # If this is a password update attempt, don't try and creating one
        if self.source == SOURCE_USER:
            return self.async_create_entry(title=self._username, data=data)

        entry = await self.async_set_unique_id(self.unique_id)
        if entry:
            self.hass.config_entries.async_update_entry(entry, data=data)
            await self.hass.config_entries.async_reload(entry.entry_id)
        return self.async_abort(reason="reauth_successful")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        icloud_dir = Store[Any](self.hass, STORAGE_VERSION, STORAGE_KEY)

        if not os.path.exists(icloud_dir.path):
            await self.hass.async_add_executor_job(os.makedirs, icloud_dir.path)

        if user_input is None:
            return self._show_setup_form(user_input, errors)

        return await self._validate_and_create_entry(user_input, "user")

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Initialise re-authentication."""
        # Store existing entry data so it can be used later and set unique ID
        # so existing config entry can be updated
        await self.async_set_unique_id(self.context.get("unique_id"))
        self._existing_entry_data = {**entry_data}
        self._description_placeholders = {"username": entry_data[CONF_USERNAME]}
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update password for a config entry that can't authenticate."""
        if user_input is None:
            return self._show_setup_form(step_id="reauth_confirm")

        return await self._validate_and_create_entry(user_input, "reauth_confirm")

    async def async_step_trusted_device(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """We need a trusted device."""
        if errors is None:
            errors = {}

        if TYPE_CHECKING:
            assert self.api is not None
        trusted_devices: list[dict[str, Any]] = await self.hass.async_add_executor_job(
            getattr, self.api, "trusted_devices"
        )
        trusted_devices_for_form: dict[int, dict[str, Any]] = {}
        for i, device in enumerate(trusted_devices):
            trusted_devices_for_form[i] = device.get(
                "deviceName", f"SMS to {device.get('phoneNumber')}"
            )

        if user_input is None:
            return await self._show_trusted_device_form(
                trusted_devices_for_form, errors
            )

        self._trusted_device = trusted_devices[int(user_input[CONF_TRUSTED_DEVICE])]

        if not await self.hass.async_add_executor_job(
            self.api.send_verification_code, self._trusted_device
        ):
            _LOGGER.error("Failed to send verification code")
            self._trusted_device = None
            errors[CONF_TRUSTED_DEVICE] = "send_verification_code"

            return await self._show_trusted_device_form(
                trusted_devices_for_form, errors
            )

        return await self.async_step_verification_code()

    async def _show_trusted_device_form(
        self, trusted_devices, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the trusted_device form to the user."""

        return self.async_show_form(
            step_id="trusted_device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TRUSTED_DEVICE): vol.All(
                        vol.Coerce(int), vol.In(trusted_devices)
                    )
                }
            ),
            errors=errors or {},
        )

    async def async_step_verification_code(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Ask the verification code to the user."""
        if errors is None:
            errors = {}

        if user_input is None:
            return await self._show_verification_code_form(errors)

        if TYPE_CHECKING:
            assert self.api is not None
            assert self._trusted_device is not None

        _verification_code: str = user_input.get(CONF_VERIFICATION_CODE, "")

        try:
            if self.api.requires_2fa:
                if not await self.hass.async_add_executor_job(
                    self.api.validate_2fa_code, _verification_code
                ):
                    raise PyiCloudException("The code you entered is not valid.")  # noqa: TRY301
            elif not await self.hass.async_add_executor_job(
                self.api.validate_verification_code,
                self._trusted_device,
                _verification_code,
            ):
                raise PyiCloudException("The code you entered is not valid.")  # noqa: TRY301
        except PyiCloudException as error:
            # Reset to the initial 2FA state to allow the user to retry
            _LOGGER.error("Failed to verify verification code: %s", error)
            self._trusted_device = None
            errors["base"] = "validate_verification_code"

            if self.api.requires_2fa:
                try:
                    self.api = await self.hass.async_add_executor_job(
                        PyiCloudService,
                        self._username,
                        self._password,
                        Store(self.hass, STORAGE_VERSION, STORAGE_KEY).path,
                        True,
                        None,
                        self._with_family,
                    )
                    return await self.async_step_verification_code(None, errors)
                except PyiCloudFailedLoginException as error_login:
                    _LOGGER.error("Error logging into iCloud service: %s", error_login)
                    self.api = None
                    errors = {CONF_PASSWORD: "invalid_auth"}
                    return self._show_setup_form(user_input, errors, "user")
            else:
                return await self.async_step_trusted_device(None, errors)

        return await self.async_step_user(
            {
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_WITH_FAMILY: self._with_family,
                CONF_MAX_INTERVAL: self._max_interval,
                CONF_GPS_ACCURACY_THRESHOLD: self._gps_accuracy_threshold,
            }
        )

    async def _show_verification_code_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the verification_code form to the user."""

        return self.async_show_form(
            step_id="verification_code",
            data_schema=vol.Schema({vol.Required(CONF_VERIFICATION_CODE): str}),
            errors=errors,
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"camera": CameraSubEntryFlowHandler}


class CameraSubEntryFlowHandler(ConfigSubentryFlow):
    """Subflow for configuring a single camera."""

    def __init__(self) -> None:
        """Initialize camera subflow."""
        self._album_id: str = ""
        self._album_type: str = ""
        self._albums: AlbumContainer | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the initial step, album type selection."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["album", "shared_stream"],
        )

    async def async_step_album(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the album selection step."""
        self._album_type = "album"
        return await self.async_step_get_album_container(user_input)

    async def async_step_shared_stream(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the shared stream selection step."""
        self._album_type = "shared_stream"
        return await self.async_step_get_album_container(user_input)

    @staticmethod
    def _get_album_container(api: PyiCloudService, album_type: str) -> AlbumContainer:
        """Return the album container based on album type."""
        if album_type == "album":
            return api.photos.albums
        return api.photos.shared_streams

    @progress_step(
        description_placeholders=lambda self: {
            "name": f"Loading {self._album_type.replace('_', ' ')}s..."
        }
    )
    async def async_step_get_album_container(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Return the album container based on album type."""
        config_entry: ConfigEntry[Any] = self._get_entry()
        api: PyiCloudService = config_entry.runtime_data.api
        self._albums = await self.hass.async_add_executor_job(
            CameraSubEntryFlowHandler._get_album_container, api, self._album_type
        )

        if self._albums is None or len(self._albums) == 0:
            if self._album_type == "album":
                _LOGGER.debug("No albums found")
                return self.async_abort(reason="no_albums")
            _LOGGER.debug("No shared streams found")
            return self.async_abort(reason="no_shared_streams")

        return self.async_show_progress_done(next_step_id="select_album")

    async def async_step_select_album(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the album selection step."""
        if user_input is not None:
            self._album_id = user_input[CONF_ALBUM_ID]
            return await self.async_step_options()

        if self._albums is None or len(self._albums) == 0:
            raise RuntimeError("Albums not loaded")

        if len(self._albums) == 1:
            self._album_id = self._albums[0].id
            return await self.async_step_options()

        _LOGGER.debug("Multiple albums found: %s", self._albums)
        options: Sequence[SelectOptionDict] = [
            {"value": album.id, "label": album.title} for album in self._albums
        ]

        schema = vol.Schema(
            {
                vol.Required(CONF_ALBUM_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.DROPDOWN,
                        sort=True,
                    )
                ),
            }
        )

        return self.async_show_form(step_id="select_album", data_schema=schema)

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the album options configuration step."""
        config_entry: ConfigEntry[Any] = self._get_entry()
        for subentry in config_entry.subentries:
            if (
                config_entry.subentries[subentry].data.get(CONF_ALBUM_ID)
                == self._album_id
            ):
                return self.async_abort(reason="already_configured")

        if user_input is not None and self._albums is not None:
            album: BasePhotoAlbum | None = self._albums.get(self._album_id)
            if album is None:
                return self.async_abort(reason="album_not_found")

            self.hass.config_entries.async_schedule_reload(config_entry.entry_id)
            return self.async_create_entry(
                title=album.title,
                data={
                    CONF_ALBUM_ID: self._album_id,
                    CONF_ALBUM_TYPE: self._album_type,
                    CONF_ALBUM_NAME: album.title,
                    **user_input,
                },
            )

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_RANDOM_ORDER,
                    default=DEFAULT_RANDOM_ORDER,
                ): BooleanSelector(),
                vol.Required(
                    CONF_PICTURE_INTERVAL,
                    default=DEFAULT_PICTURE_INTERVAL,
                ): float,
            }
        )

        return self.async_show_form(step_id="options", data_schema=schema)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to modify an existing camera entity."""
        # Retrieve the parent config entry for reference.
        config_entry: ConfigEntry[Any] = self._get_entry()
        # Retrieve the specific subentry targeted for update.
        config_subentry: ConfigSubentry = self._get_reconfigure_subentry()

        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry=config_entry,
                subentry=config_subentry,
                data_updates=user_input,
            )

        data = config_subentry.data
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_RANDOM_ORDER,
                    default=data.get(CONF_RANDOM_ORDER, DEFAULT_RANDOM_ORDER),
                ): BooleanSelector(),
                vol.Required(
                    CONF_PICTURE_INTERVAL,
                    default=data.get(CONF_PICTURE_INTERVAL, DEFAULT_PICTURE_INTERVAL),
                ): float,
            }
        )

        return self.async_show_form(step_id="reconfigure", data_schema=schema)
