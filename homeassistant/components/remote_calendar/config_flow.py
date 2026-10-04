"""Config flow for Remote Calendar integration."""

from http import HTTPStatus
import logging
from typing import Any, override

from httpx import HTTPError, InvalidURL, TimeoutException
import probatio

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.helpers.httpx_client import get_async_client

from .client import get_calendar
from .const import CONF_CALENDAR_NAME, DOMAIN
from .ics import InvalidIcsException, parse_calendar

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_CALENDAR_NAME): str,
        probatio.Required(CONF_URL): str,
        probatio.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)

STEP_RECONFIGURE_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_URL): str,
        probatio.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)

STEP_AUTH_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(CONF_PASSWORD): str,
    }
)


class RemoteCalendarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Remote Calendar."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self.data: dict[str, Any] = {}

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the calendar URL."""
        return await self.async_step_user()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step, also used to reconfigure the calendar URL."""
        entry: ConfigEntry | None = None
        data_schema = STEP_USER_DATA_SCHEMA
        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            data_schema = STEP_RECONFIGURE_DATA_SCHEMA
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(
                    data_schema, entry.data if entry else {}
                ),
            )

        user_input[CONF_URL] = _normalize_url(user_input[CONF_URL])
        if entry:
            user_input[CONF_CALENDAR_NAME] = entry.data[CONF_CALENDAR_NAME]
            if user_input[CONF_URL] != entry.data[CONF_URL]:
                self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})
        else:
            self._async_abort_entries_match(
                {CONF_CALENDAR_NAME: user_input[CONF_CALENDAR_NAME]}
            )
            self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})

        errors: dict[str, str] = {}
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
                    errors["base"] = "invalid_ics_file"
                else:
                    return self._async_finish(user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(data_schema, user_input),
            errors=errors,
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the authentication step."""
        if user_input is None:
            suggested: dict[str, Any] = {}
            if self.source == SOURCE_RECONFIGURE:
                suggested = {
                    CONF_USERNAME: self._get_reconfigure_entry().data.get(CONF_USERNAME)
                }
            return self.async_show_form(
                step_id="auth",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_AUTH_DATA_SCHEMA, suggested
                ),
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
                    return self._async_finish(
                        {
                            **self.data,
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        }
                    )

        return self.async_show_form(
            step_id="auth",
            data_schema=self.add_suggested_values_to_schema(
                STEP_AUTH_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    def _async_finish(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create the entry, or replace the data of the reconfigured one."""
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), data=data
            )
        return self.async_create_entry(title=data[CONF_CALENDAR_NAME], data=data)


def _normalize_url(url: str) -> str:
    """Rewrite a webcal:// URL to https://."""
    if url.startswith("webcal://"):
        return url.replace("webcal://", "https://", 1)
    return url
