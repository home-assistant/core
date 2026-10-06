"""Config flow for simplepush integration."""

from http import HTTPStatus
from typing import Any, override

import probatio
from simplepush import ApiError, Client
from simplepush.legacy import UnknownError, send

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_NAME, CONF_PASSWORD

from .const import (
    APP_TITLE,
    ATTR_ENCRYPTED,
    CONF_DEVICE_KEY,
    CONF_SALT,
    DEFAULT_NAME,
    DOMAIN,
)


def validate_input(api_token: str) -> dict[str, str] | None:
    """Send a test task to your own devices."""
    try:
        Client(api_token=api_token).send_task(
            title="Home Assistant configured successfully",
            content=(
                "Your Home Assistant Simplepush integration is configured correctly "
                "and ready to send notifications to this device."
            ),
        )
    except ApiError as err:
        if err.status == HTTPStatus.UNAUTHORIZED:
            return {"base": "invalid_auth"}
        return {"base": "cannot_connect"}
    except OSError:
        return {"base": "cannot_connect"}

    return None


def validate_legacy_input(entry: dict[str, str]) -> dict[str, str] | None:
    """Send a test message to a device of the old app."""
    try:
        if CONF_PASSWORD in entry:
            send(
                key=entry[CONF_DEVICE_KEY],
                password=entry[CONF_PASSWORD],
                salt=entry[CONF_SALT],
                title="HA test",
                message="Message delivered successfully",
            )
        else:
            send(
                key=entry[CONF_DEVICE_KEY],
                title="HA test",
                message="Message delivered successfully",
            )
    except UnknownError:
        return {"base": "cannot_connect"}

    return None


class SimplePushFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for simplepush."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose between the current and the old Simplepush app."""
        return self.async_show_menu(step_id="user", menu_options=["app", "legacy"])

    async def async_step_app(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up the current Simplepush app with an API token."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_API_TOKEN: user_input[CONF_API_TOKEN]}
            )

            if not (
                errors := await self.hass.async_add_executor_job(
                    validate_input, user_input[CONF_API_TOKEN]
                )
            ):
                return self.async_create_entry(title=APP_TITLE, data=user_input)

        return self.async_show_form(
            step_id="app",
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_API_TOKEN)): str}
            ),
            errors=errors,
        )

    async def async_step_legacy(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up the old Simplepush app with a device key."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_DEVICE_KEY])
            self._abort_if_unique_id_configured()

            self._async_abort_entries_match(
                {
                    CONF_NAME: user_input[CONF_NAME],
                }
            )

            if not (
                errors := await self.hass.async_add_executor_job(
                    validate_legacy_input, user_input
                )
            ):
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="legacy",
            data_schema=probatio.Schema(
                {
                    probatio.Required(probatio.Secret(CONF_DEVICE_KEY)): str,
                    # Name field is no longer allowed in config flow schemas
                    # pylint: disable-next=home-assistant-config-flow-name-field
                    probatio.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    probatio.Inclusive(
                        probatio.Secret(CONF_PASSWORD), ATTR_ENCRYPTED
                    ): str,
                    probatio.Inclusive(CONF_SALT, ATTR_ENCRYPTED): str,
                }
            ),
            errors=errors,
        )
