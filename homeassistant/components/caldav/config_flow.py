"""Configuration flow for CalDav."""

from collections.abc import Mapping, Sequence
import logging
import re
from typing import Any

import caldav
from caldav.lib.error import AuthorizationError, DAVError
import requests
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,
)
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    CONF_LEGACY_ENTITY_NAMES,
    CONF_READ_ONLY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SCAN_INTERVAL_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD, default=""): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Optional(CONF_LEGACY_ENTITY_NAMES, default=True): cv.boolean,
        vol.Optional(CONF_READ_ONLY, default=False): cv.boolean,
    }
)


class CalDavConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for caldav."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_URL: user_input[CONF_URL],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                }
            )
            if error := await self._test_connection(user_input):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def _test_connection(self, user_input: dict[str, Any]) -> str | None:
        """Test the connection to the CalDAV server and return an error if any."""
        client = caldav.DAVClient(
            user_input[CONF_URL],
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
            ssl_verify_cert=user_input[CONF_VERIFY_SSL],
        )
        try:
            await self.hass.async_add_executor_job(client.principal)
        except AuthorizationError as err:
            _LOGGER.warning("Authorization Error connecting to CalDAV server: %s", err)
            if err.reason == "Unauthorized":
                return "invalid_auth"
            # AuthorizationError can be raised if the url is incorrect or
            # on some other unexpected server response.
            return "cannot_connect"
        except requests.ConnectionError as err:
            _LOGGER.warning("Connection Error connecting to CalDAV server: %s", err)
            return "cannot_connect"
        except DAVError as err:
            _LOGGER.warning("CalDAV client error: %s", err)
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        return None

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        errors = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            user_input = {**reauth_entry.data, **user_input}

            if error := await self._test_connection(user_input):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(reauth_entry, data=user_input)

        return self.async_show_form(
            description_placeholders={
                CONF_USERNAME: reauth_entry.data[CONF_USERNAME],
            },
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow handler."""
        return CalDAVOptionsFlowHandler()


class CalDAVOptionsFlowHandler(OptionsFlowWithReload):
    """Handle CalDAV integration options."""

    def parse_interval(self, interval_str: str) -> int:
        """Parse an interval string into total seconds.

        Supported formats:
        - Word-based: '15 s', '20 min', '2h', '1 min 30 s', '1h 15m 10s'
        - Colon-based: 'MM:SS', 'HH:MM:SS'
        - Plain number (defaults to seconds): '45'
        """
        s = interval_str.strip().lower()

        # --- Case 1: Colon-based format ---
        if re.match(r"^\d+(:\d+){1,2}$", s):
            parts = list(map(int, s.split(":")))
            if len(parts) == 2:  # MM:SS
                minutes, seconds = parts
                return minutes * 60 + seconds
            if len(parts) == 3:  # HH:MM:SS
                hours, minutes, seconds = parts
                return hours * 3600 + minutes * 60 + seconds

        # --- Case 2: Word-based format ---
        units = {
            "s": 1,
            "sec": 1,
            "secs": 1,
            "second": 1,
            "seconds": 1,
            "m": 60,
            "min": 60,
            "mins": 60,
            "minute": 60,
            "minutes": 60,
            "h": 3600,
            "hr": 3600,
            "hrs": 3600,
            "hour": 3600,
            "hours": 3600,
            "d": 86400,
            "day": 86400,
            "days": 86400,
        }

        matches = re.findall(r"(\d+)\s*([a-z]*)", s)
        if matches:
            total_seconds = 0
            for value, unit in matches:
                value = int(value)
                if unit == "":  # no unit → seconds
                    total_seconds += value
                elif unit in units:
                    total_seconds += value * units[unit]
                else:
                    raise ValueError(f"Unsupported time unit: '{unit}'")
            return total_seconds

        # --- Case 3: Just a number (defaults to seconds) ---
        if s.isdigit():
            return int(s)

        raise ValueError(f"Invalid interval format: '{interval_str}'")

    def format_interval(self, seconds: int) -> str:
        """Convert seconds into a human-friendly string like: '1 hour, 2 minutes, 3 seconds'."""
        if seconds < 0:
            raise ValueError("Interval cannot be negative")

        parts = []
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)

        if days:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds or not parts:  # show "0 seconds" if total was 0
            parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

        return ", ".join(parts)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the options flow initialization step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # copy existing data so we don't lose anything not in the options form
            for key in self.config_entry.data:
                if key not in (
                    CONF_READ_ONLY,
                    CONF_SCAN_INTERVAL,
                ):  # exclude keys managed by options flow
                    user_input[key] = self.config_entry.data[key]
            # update the config entry data with new read_only value
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=user_input, options=self.config_entry.options
            )

            raw = str(user_input.get(CONF_SCAN_INTERVAL))
            # UI returns strings for custom_value, so coerce
            try:
                interval = self.parse_interval(raw)
            except (TypeError, ValueError):
                errors["scan_interval"] = "invalid_interval"
            else:
                if not (MIN_SCAN_INTERVAL <= interval <= MAX_SCAN_INTERVAL):
                    errors["scan_interval"] = "out_of_range"
                else:
                    _LOGGER.info("Config option set: scan_interval raw value: %s", raw)
                    # save integer seconds into options
                    # also we need to save read_only in options so it triggers reload
                    # when changed, as it's used in calendar entity init.
                    # Alternatively we could also trigger reload: await self.hass.config_entries.async_reload
                    return self.async_create_entry(
                        title="",
                        data={
                            CONF_SCAN_INTERVAL: interval,
                            CONF_READ_ONLY: user_input[CONF_READ_ONLY],
                        },
                    )

        # Build options list for the select; values are strings so user can type as well
        scan_interval_default_values: Sequence[selector.SelectOptionDict] = [
            {"value": str(val), "label": self.format_interval(val)}
            for val in SCAN_INTERVAL_OPTIONS
        ]

        data_schema = vol.Schema(
            {
                # read_only gets its default from config_entry data: see https://community.home-assistant.io/t/configflowhandler-and-optionsflowhandler-managing-the-same-parameter/365582/4
                vol.Optional(
                    CONF_READ_ONLY,
                    default=self.config_entry.data[CONF_READ_ONLY],
                ): cv.boolean,
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.format_interval(
                        self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        )
                    ),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=scan_interval_default_values,
                        custom_value=True,  # allow typing a custom value in the combobox
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=errors
        )
