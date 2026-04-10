"""Config flow for Eufy Security integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from eufy_security import (
    CannotConnectError,
    CaptchaRequiredError,
    EufySecurityAPI,
    EufySecurityError,
    InvalidCaptchaError,
    InvalidCredentialsError,
    async_login,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_CONFIG_ENTRY_MINOR_VERSION,
    CONF_RTSP_CREDENTIALS,
    CONF_RTSP_PASSWORD,
    CONF_RTSP_USERNAME,
    CONF_SESSION_STATE,
    DOMAIN,
)
from .coordinator import EufySecurityConfigEntry

CONF_CAPTCHA_ID = "captcha_id"
CONF_CAPTCHA_CODE = "captcha_code"

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_CAPTCHA_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CAPTCHA_CODE): str,
    }
)


class EufySecurityConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eufy Security."""

    VERSION = 1
    MINOR_VERSION = CONF_CONFIG_ENTRY_MINOR_VERSION

    @staticmethod
    def async_get_options_flow(
        config_entry: EufySecurityConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return EufySecurityOptionsFlowHandler()

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._pending_credentials: dict[str, str] = {}
        self._captcha_id: str | None = None
        self._captcha_image: str | None = None
        self._pending_api: EufySecurityAPI | None = None

    def _get_captcha_img_tag(self, captcha_image: str | None) -> str:
        """Return an HTML img tag for the CAPTCHA image."""
        if not captcha_image or not captcha_image.startswith("data:image/"):
            return ""
        return f"![CAPTCHA]({captcha_image})"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            try:
                api = await async_login(
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                    session,
                )
            except CaptchaRequiredError as err:
                # Store credentials and API instance for CAPTCHA retry
                self._pending_credentials = user_input
                self._captcha_id = err.captcha_id
                self._captcha_image = err.captcha_image
                self._pending_api = err.api
                return await self.async_step_captcha()
            except InvalidCredentialsError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except EufySecurityError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_SESSION_STATE: api.get_session_state(),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_captcha(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the CAPTCHA verification step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                # Reuse the stored API instance to maintain the same ECDH keys
                api = await async_login(
                    self._pending_credentials[CONF_EMAIL],
                    self._pending_credentials[CONF_PASSWORD],
                    session,
                    captcha_id=self._captcha_id,
                    captcha_code=user_input[CONF_CAPTCHA_CODE],
                    api=self._pending_api,
                )
            except CaptchaRequiredError as err:
                # CAPTCHA was wrong, try again with new image
                self._captcha_id = err.captcha_id
                self._captcha_image = err.captcha_image
                self._pending_api = err.api
                errors["base"] = "invalid_captcha"
            except InvalidCaptchaError:
                # CAPTCHA was wrong but server didn't provide new one - request fresh
                _LOGGER.debug("Invalid CAPTCHA, requesting new one")
                try:
                    await async_login(
                        self._pending_credentials[CONF_EMAIL],
                        self._pending_credentials[CONF_PASSWORD],
                        session,
                    )
                except CaptchaRequiredError as err:
                    self._captcha_id = err.captcha_id
                    self._captcha_image = err.captcha_image
                    self._pending_api = err.api
                errors["base"] = "invalid_captcha"
            except InvalidCredentialsError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except EufySecurityError as err:
                _LOGGER.warning("API error: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=self._pending_credentials[CONF_EMAIL],
                    data={
                        CONF_EMAIL: self._pending_credentials[CONF_EMAIL],
                        CONF_PASSWORD: self._pending_credentials[CONF_PASSWORD],
                        CONF_SESSION_STATE: api.get_session_state(),
                    },
                )

        return self.async_show_form(
            step_id="captcha",
            data_schema=STEP_CAPTCHA_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "captcha_img": self._get_captcha_img_tag(self._captcha_image),
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            credentials = {
                CONF_EMAIL: reauth_entry.data[CONF_EMAIL],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            session = async_get_clientsession(self.hass)
            try:
                api = await async_login(
                    credentials[CONF_EMAIL],
                    credentials[CONF_PASSWORD],
                    session,
                )
            except CaptchaRequiredError as err:
                # Store credentials and API instance for CAPTCHA retry
                self._pending_credentials = credentials
                self._captcha_id = err.captcha_id
                self._captcha_image = err.captcha_image
                self._pending_api = err.api
                return await self.async_step_reauth_captcha()
            except InvalidCredentialsError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except EufySecurityError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        **credentials,
                        CONF_SESSION_STATE: api.get_session_state(),
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                CONF_EMAIL: reauth_entry.data[CONF_EMAIL],
            },
        )

    async def async_step_reauth_captcha(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle CAPTCHA verification during reauthentication."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                # Reuse the stored API instance to maintain the same ECDH keys
                api = await async_login(
                    self._pending_credentials[CONF_EMAIL],
                    self._pending_credentials[CONF_PASSWORD],
                    session,
                    captcha_id=self._captcha_id,
                    captcha_code=user_input[CONF_CAPTCHA_CODE],
                    api=self._pending_api,
                )
            except CaptchaRequiredError as err:
                # CAPTCHA was wrong, try again with new image
                self._captcha_id = err.captcha_id
                self._captcha_image = err.captcha_image
                self._pending_api = err.api
                errors["base"] = "invalid_captcha"
            except InvalidCaptchaError:
                # CAPTCHA was wrong but server didn't provide new one - request fresh
                _LOGGER.debug("Invalid CAPTCHA, requesting new one")
                try:
                    await async_login(
                        self._pending_credentials[CONF_EMAIL],
                        self._pending_credentials[CONF_PASSWORD],
                        session,
                    )
                except CaptchaRequiredError as err:
                    self._captcha_id = err.captcha_id
                    self._captcha_image = err.captcha_image
                    self._pending_api = err.api
                errors["base"] = "invalid_captcha"
            except InvalidCredentialsError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except EufySecurityError as err:
                _LOGGER.warning("API error: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        **self._pending_credentials,
                        CONF_SESSION_STATE: api.get_session_state(),
                    },
                )

        return self.async_show_form(
            step_id="reauth_captcha",
            data_schema=STEP_CAPTCHA_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "captcha_img": self._get_captcha_img_tag(self._captcha_image),
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            # Check unique ID before attempting login to abort early
            await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
            self._abort_if_unique_id_mismatch()

            session = async_get_clientsession(self.hass)
            try:
                api = await async_login(
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                    session,
                )
            except CaptchaRequiredError as err:
                # Store credentials and API instance for CAPTCHA retry
                self._pending_credentials = user_input
                self._captcha_id = err.captcha_id
                self._captcha_image = err.captcha_image
                self._pending_api = err.api
                return await self.async_step_reconfigure_captcha()
            except InvalidCredentialsError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except EufySecurityError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_SESSION_STATE: api.get_session_state(),
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_EMAIL, default=reconfigure_entry.data.get(CONF_EMAIL, "")
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure_captcha(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle CAPTCHA verification during reconfiguration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            # Check unique ID before attempting login to abort early
            await self.async_set_unique_id(
                self._pending_credentials[CONF_EMAIL].lower()
            )
            self._abort_if_unique_id_mismatch()

            session = async_get_clientsession(self.hass)
            try:
                # Reuse the stored API instance to maintain the same ECDH keys
                api = await async_login(
                    self._pending_credentials[CONF_EMAIL],
                    self._pending_credentials[CONF_PASSWORD],
                    session,
                    captcha_id=self._captcha_id,
                    captcha_code=user_input[CONF_CAPTCHA_CODE],
                    api=self._pending_api,
                )
            except CaptchaRequiredError as err:
                # CAPTCHA was wrong, try again with new image
                self._captcha_id = err.captcha_id
                self._captcha_image = err.captcha_image
                self._pending_api = err.api
                errors["base"] = "invalid_captcha"
            except InvalidCaptchaError:
                # CAPTCHA was wrong but server didn't provide new one - request fresh
                _LOGGER.debug("Invalid CAPTCHA, requesting new one")
                try:
                    await async_login(
                        self._pending_credentials[CONF_EMAIL],
                        self._pending_credentials[CONF_PASSWORD],
                        session,
                    )
                except CaptchaRequiredError as err:
                    self._captcha_id = err.captcha_id
                    self._captcha_image = err.captcha_image
                    self._pending_api = err.api
                errors["base"] = "invalid_captcha"
            except InvalidCredentialsError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except EufySecurityError as err:
                _LOGGER.warning("API error: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data={
                        CONF_EMAIL: self._pending_credentials[CONF_EMAIL],
                        CONF_PASSWORD: self._pending_credentials[CONF_PASSWORD],
                        CONF_SESSION_STATE: api.get_session_state(),
                    },
                )

        return self.async_show_form(
            step_id="reconfigure_captcha",
            data_schema=STEP_CAPTCHA_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "captcha_img": self._get_captcha_img_tag(self._captcha_image),
            },
        )


class EufySecurityOptionsFlowHandler(OptionsFlow):
    """Handle Eufy Security options."""

    def __init__(self) -> None:
        """Initialize options flow."""
        self._camera_serials: list[str] = []
        self._camera_index: int = 0
        self._rtsp_credentials: dict[str, dict[str, str]] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Initialize the options flow and start camera configuration."""
        cameras = self._get_live_cameras()

        if not cameras:
            return self.async_abort(reason="no_cameras")

        # Store camera list and existing credentials
        self._camera_serials = list(cameras.keys())
        self._rtsp_credentials = dict(
            self.config_entry.options.get(CONF_RTSP_CREDENTIALS, {})
        )
        self._camera_index = 0

        # Start configuring the first camera
        return await self.async_step_camera()

    def _get_live_cameras(self) -> dict[str, Any]:
        """Get cameras from live runtime data sources."""
        runtime_data = self.config_entry.runtime_data
        if runtime_data is None:
            return {}
        api = getattr(runtime_data, "api", None)
        if api is not None and getattr(api, "cameras", None) is not None:
            cameras: dict[str, Any] = api.cameras
            return cameras
        result: dict[str, Any] = runtime_data.devices.get("cameras", {})
        return result

    async def async_step_camera(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure RTSP credentials for a single camera."""
        cameras = self._get_live_cameras()

        if self._camera_index >= len(self._camera_serials):
            # All cameras configured, save and exit
            return self.async_create_entry(
                title="", data={CONF_RTSP_CREDENTIALS: self._rtsp_credentials}
            )

        serial = self._camera_serials[self._camera_index]
        camera = cameras.get(serial)

        if user_input is not None:
            # Save credentials for this camera
            username = user_input.get(CONF_RTSP_USERNAME, "").strip()
            password = user_input.get(CONF_RTSP_PASSWORD, "").strip()

            # Preserve existing password if user provided a username but left password empty
            if username and not password:
                current_creds = self._rtsp_credentials.get(serial, {})
                password = current_creds.get("password", "")

            if username or password:
                self._rtsp_credentials[serial] = {
                    "username": username,
                    "password": password,
                }
            elif serial in self._rtsp_credentials:
                # Clear credentials if both fields empty
                del self._rtsp_credentials[serial]

            # Move to next camera
            self._camera_index += 1
            return await self.async_step_camera()

        # Get current credentials for this camera
        current_creds = self._rtsp_credentials.get(serial, {})
        current_username = current_creds.get("username", "")

        # Build camera info for display
        camera_name = camera.name if camera else serial
        camera_ip = camera.ip_address if camera else None

        schema = vol.Schema(
            {
                vol.Optional(CONF_RTSP_USERNAME, default=current_username): str,
                vol.Optional(CONF_RTSP_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="camera",
            data_schema=schema,
            description_placeholders={
                "camera_name": camera_name,
                "camera_ip": camera_ip or "Not available",
                "camera_number": str(self._camera_index + 1),
                "total_cameras": str(len(self._camera_serials)),
            },
        )
