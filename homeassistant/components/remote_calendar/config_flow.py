"""Config flow for Remote Calendar integration."""

from http import HTTPStatus
import logging
from typing import Any

from httpx import HTTPError, InvalidURL, TimeoutException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.helpers.httpx_client import get_async_client

from .client import get_calendar
from .const import CONF_CALENDAR_NAME, DOMAIN
from .ics import InvalidIcsException, parse_calendar

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CALENDAR_NAME): str,
        vol.Required(CONF_URL): str,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)

STEP_AUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class RemoteCalendarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Remote Calendar."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self.data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )
        errors: dict[str, str] = {}
        self._async_abort_entries_match(
            {CONF_CALENDAR_NAME: user_input[CONF_CALENDAR_NAME]}
        )
        if user_input[CONF_URL].startswith("webcal://"):
            user_input[CONF_URL] = user_input[CONF_URL].replace(
                "webcal://", "https://", 1
            )
        self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})
        client = get_async_client(self.hass, verify_ssl=user_input[CONF_VERIFY_SSL])
        try:
            res = await get_calendar(client, user_input[CONF_URL])
            if res.status_code == HTTPStatus.UNAUTHORIZED:
                www_auth = res.headers.get("www-authenticate", "").lower()
                if "basic" in www_auth:
                    self.data = user_input
                    return await self.async_step_auth()
            if res.status_code == HTTPStatus.FORBIDDEN:
                errors["base"] = "forbidden"
                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors=errors,
                )
            res.raise_for_status()
        except TimeoutException as err:
            errors["base"] = "timeout_connect"
            _LOGGER.debug(
                "A timeout error occurred: %s", str(err) or type(err).__name__
            )
        except (HTTPError, InvalidURL) as err:
            errors["base"] = "cannot_connect"
            _LOGGER.debug("An error occurred: %s", str(err) or type(err).__name__)
        else:
            try:
                await parse_calendar(self.hass, res.text)
            except InvalidIcsException:
                errors["base"] = "invalid_ics_file"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_CALENDAR_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the authentication step."""
        if user_input is None:
            return self.async_show_form(
                step_id="auth",
                data_schema=STEP_AUTH_DATA_SCHEMA,
            )

        errors: dict[str, str] = {}
        client = get_async_client(self.hass, verify_ssl=self.data[CONF_VERIFY_SSL])
        try:
            res = await get_calendar(
                client,
                self.data[CONF_URL],
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
            )
            if res.status_code == HTTPStatus.UNAUTHORIZED:
                errors["base"] = "invalid_auth"
            elif res.status_code == HTTPStatus.FORBIDDEN:
                return self.async_abort(reason="forbidden")
            else:
                res.raise_for_status()
        except TimeoutException as err:
            errors["base"] = "timeout_connect"
            _LOGGER.debug(
                "A timeout error occurred: %s", str(err) or type(err).__name__
            )
        except (HTTPError, InvalidURL) as err:
            errors["base"] = "cannot_connect"
            _LOGGER.debug("An error occurred: %s", str(err) or type(err).__name__)
        else:
            if not errors:
                try:
                    await parse_calendar(self.hass, res.text)
                except InvalidIcsException:
                    return self.async_abort(reason="invalid_ics_file")
                else:
                    return self.async_create_entry(
                        title=self.data[CONF_CALENDAR_NAME],
                        data={
                            **self.data,
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        },
                    )

        return self.async_show_form(
            step_id="auth",
            data_schema=self.add_suggested_values_to_schema(
                STEP_AUTH_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
