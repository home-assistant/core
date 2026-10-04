"""Config flow for simplepush integration."""

import hashlib
from typing import Any, override

import probatio
from simplepush import ApiError, Client
from simplepush.legacy import UnknownError, send

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_NAME, CONF_PASSWORD

from .const import (
    ATTR_ENCRYPTED,
    CONF_DEVICE_KEY,
    CONF_SALT,
    CONF_TOPIC,
    DEFAULT_NAME,
    DOMAIN,
)


def validate_input(api_token: str, topic: str | None) -> dict[str, str] | None:
    """Send a test task to your own devices, or to `topic`."""
    try:
        Client(api_token=api_token).send_task(
            topic=topic,
            title="HA test",
            content="Message delivered successfully",
        )
    except ApiError as err:
        if err.status == 401:
            return {"base": "invalid_auth"}
        if err.status in (403, 404):
            return {"base": "topic_not_joined"}
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


def _token_unique_id(api_token: str) -> str:
    return hashlib.sha256(api_token.encode()).hexdigest()[:16]


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
            await self.async_set_unique_id(_token_unique_id(user_input[CONF_API_TOKEN]))
            self._abort_if_unique_id_configured()

            self._async_abort_entries_match(
                {
                    CONF_NAME: user_input[CONF_NAME],
                }
            )

            if not (
                errors := await self.hass.async_add_executor_job(
                    validate_input, user_input[CONF_API_TOKEN], None
                )
            ):
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="app",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_API_TOKEN): str,
                    # Name field is no longer allowed in config flow schemas
                    # pylint: disable-next=home-assistant-config-flow-name-field
                    probatio.Required(CONF_NAME, default=DEFAULT_NAME): str,
                }
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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set a new API token, or move an old app entry to the current app.

        The old app's device key becomes a topic in the current app, so an
        old entry keeps reaching the same devices through that topic.
        """
        entry = self._get_reconfigure_entry()
        topic: str | None = entry.data.get(CONF_TOPIC, entry.data.get(CONF_DEVICE_KEY))
        errors: dict[str, str] | None = None
        if user_input is not None:
            api_token = user_input[CONF_API_TOKEN]
            unique_id = entry.unique_id if topic else _token_unique_id(api_token)
            if any(
                other.unique_id == unique_id and other.entry_id != entry.entry_id
                for other in self._async_current_entries(include_ignore=False)
            ):
                return self.async_abort(reason="already_configured")

            if not (
                errors := await self.hass.async_add_executor_job(
                    validate_input, api_token, topic
                )
            ):
                data: dict[str, Any] = {
                    CONF_API_TOKEN: api_token,
                    CONF_NAME: entry.data[CONF_NAME],
                }
                if topic:
                    data[CONF_TOPIC] = topic
                return self.async_update_reload_and_abort(
                    entry, unique_id=unique_id, data=data
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=probatio.Schema({probatio.Required(CONF_API_TOKEN): str}),
            description_placeholders={"name": entry.title},
            errors=errors,
        )
