"""Config flow for Remote Calendar integration."""

from http import HTTPStatus
import logging
from typing import Any

from httpx import HTTPError, InvalidURL, TimeoutException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.helpers.httpx_client import get_async_client

from .client import get_calendar
from .const import CONF_CALENDAR_NAME, DOMAIN
from .ics import InvalidIcsException, parse_calendar

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CALENDAR_NAME): str,
        vol.Required(CONF_URL): str,
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
        self.url: str | None = None
        self.calendar_name: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )
        errors: dict = {}
        _LOGGER.debug("User input: %s", user_input)
        self._async_abort_entries_match(
            {CONF_CALENDAR_NAME: user_input[CONF_CALENDAR_NAME]}
        )
        if user_input[CONF_URL].startswith("webcal://"):
            user_input[CONF_URL] = user_input[CONF_URL].replace(
                "webcal://", "https://", 1
            )
            _LOGGER.debug(
                "Converted webcal:// to https:// URL: %s", user_input[CONF_URL]
            )
        self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})
        client = get_async_client(self.hass)

        try:
            _LOGGER.debug("Attempting to fetch calendar from URL")
            res = await get_calendar(client, user_input[CONF_URL])
            _LOGGER.debug(
                "Calendar fetch completed with status code: %s", res.status_code
            )

            if res.status_code == HTTPStatus.UNAUTHORIZED:
                _LOGGER.warning(
                    "Received 401 Unauthorized for URL. Response headers: %s",
                    dict(res.headers),
                )
                # Store URL and calendar name for auth step
                self.url = user_input[CONF_URL]  # pylint: disable=attribute-defined-outside-init
                self.calendar_name = user_input[CONF_CALENDAR_NAME]  # pylint: disable=attribute-defined-outside-init
                return await self.async_step_auth()
            if res.status_code == HTTPStatus.FORBIDDEN:
                _LOGGER.warning(
                    "Received 403 Forbidden for URL. Response headers: %s",
                    dict(res.headers),
                )
                errors["base"] = "forbidden"
                return self.async_show_form(
                    step_id="user",
                    data_schema=self.add_suggested_values_to_schema(
                        STEP_USER_DATA_SCHEMA, user_input
                    ),
                    errors=errors,
                )
            res.raise_for_status()
            _LOGGER.debug(
                "Calendar fetch successful, content length: %s bytes", len(res.text)
            )
        except TimeoutException as err:
            errors["base"] = "timeout_connect"
            _LOGGER.debug(
                "A timeout error occurred: %s", str(err) or type(err).__name__
            )
        except (HTTPError, InvalidURL) as err:
            errors["base"] = "cannot_connect"
            _LOGGER.debug(
                "An HTTP error occurred: %s (type: %s)",
                str(err) or type(err).__name__,
                type(err).__name__,
            )
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
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the authentication step."""
        assert self.url is not None
        assert self.calendar_name is not None
        errors: dict = {}
        if user_input is None:
            return self.async_show_form(
                step_id="auth",
                data_schema=STEP_AUTH_DATA_SCHEMA,
                errors=errors,
            )

        _LOGGER.debug("Auth step user input received")
        client = get_async_client(self.hass)

        try:
            _LOGGER.debug("Attempting to fetch calendar with authentication")
            res = await get_calendar(
                client,
                str(self.url),
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
            )
            _LOGGER.debug(
                "Calendar fetch with auth completed with status code: %s",
                res.status_code,
            )

            if res.status_code == HTTPStatus.UNAUTHORIZED:
                errors["base"] = "unauthorized"
                return self.async_show_form(
                    step_id="auth",
                    data_schema=self.add_suggested_values_to_schema(
                        STEP_AUTH_DATA_SCHEMA, user_input
                    ),
                    errors=errors,
                )
            if res.status_code == HTTPStatus.FORBIDDEN:
                errors["base"] = "forbidden"
                return self.async_show_form(
                    step_id="auth",
                    data_schema=self.add_suggested_values_to_schema(
                        STEP_AUTH_DATA_SCHEMA, user_input
                    ),
                    errors=errors,
                )
            res.raise_for_status()
            _LOGGER.debug(
                "Calendar fetch with auth successful, content length: %s bytes",
                len(res.text),
            )
        except TimeoutException as err:
            errors["base"] = "timeout_connect"
            _LOGGER.debug(
                "A timeout error occurred: %s", str(err) or type(err).__name__
            )
        except (HTTPError, InvalidURL) as err:
            errors["base"] = "cannot_connect"
            _LOGGER.debug(
                "An HTTP error occurred: %s (type: %s)",
                str(err) or type(err).__name__,
                type(err).__name__,
            )
        else:
            try:
                await parse_calendar(self.hass, res.text)
            except InvalidIcsException:
                errors["base"] = "invalid_ics_file"
            else:
                # Combine URL, calendar name, and auth credentials
                entry_data = {
                    CONF_CALENDAR_NAME: self.calendar_name,
                    CONF_URL: self.url,
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                }
                return self.async_create_entry(
                    title=str(self.calendar_name), data=entry_data
                )

        return self.async_show_form(
            step_id="auth",
            data_schema=self.add_suggested_values_to_schema(
                STEP_AUTH_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
