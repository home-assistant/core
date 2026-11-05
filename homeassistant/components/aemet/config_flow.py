"""Config flow for AEMET OpenData."""

from collections.abc import Mapping
from typing import Any, override

from aemet_opendata.exceptions import AemetError, AuthError
from aemet_opendata.interface import AEMET, ConnectionOptions
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.selector import (
    DateSelector,
    LocationSelector,
    LocationSelectorConfig,
)
from homeassistant.util import dt as dt_util

from .const import (
    API_KEY_URL,
    CONF_API_KEY_DATE,
    CONF_API_KEY_REMINDER,
    CONF_RADAR_UPDATES,
    CONF_STATION_UPDATES,
    DEFAULT_NAME,
    DOMAIN,
)
from .coordinator import AemetConfigEntry
from .util import parse_issue_date


class _OptionalDateSelector(DateSelector):
    """Date selector that allows the field to be cleared."""

    @override
    def __call__(self, data: Any) -> Any:
        """Validate the passed selection, allowing an empty value."""
        if data is None or data == "":
            return data
        return super().__call__(data)


async def _async_validate_api_key(
    hass: HomeAssistant,
    api_key: str,
    latitude: float,
    longitude: float,
) -> str | None:
    """Validate an API key by querying AEMET for the given coordinates."""
    options = ConnectionOptions(api_key)
    aemet = AEMET(aiohttp_client.async_get_clientsession(hass), options)
    try:
        await aemet.select_coordinates(latitude, longitude)
    except AuthError:
        return "invalid_api_key"
    except AemetError:
        return "cannot_connect"
    return None


class AemetOptionsFlow(OptionsFlow):
    """Options flow for AEMET OpenData."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage AEMET OpenData options."""
        errors: dict[str, str] = {}
        entry = self.config_entry
        current_options = {
            CONF_RADAR_UPDATES: entry.options.get(CONF_RADAR_UPDATES, False),
            CONF_STATION_UPDATES: entry.options.get(CONF_STATION_UPDATES, True),
            CONF_API_KEY_REMINDER: entry.options.get(CONF_API_KEY_REMINDER, False),
        }
        current_issue_date = parse_issue_date(entry.data.get(CONF_API_KEY_DATE))
        current_values = {
            **current_options,
        }

        if user_input is not None:
            new_api_key = user_input.get(CONF_API_KEY)
            reminder_enabled = user_input[CONF_API_KEY_REMINDER]
            issue_date_input = user_input.get(CONF_API_KEY_DATE)
            issue_date = parse_issue_date(issue_date_input)
            today = dt_util.now().date()

            if (issue_date_input and issue_date is None) or (
                issue_date is not None and issue_date > today
            ):
                errors[CONF_API_KEY_DATE] = "invalid_date"

            if new_api_key and new_api_key != entry.data[CONF_API_KEY]:
                error = await _async_validate_api_key(
                    self.hass,
                    new_api_key,
                    entry.data[CONF_LATITUDE],
                    entry.data[CONF_LONGITUDE],
                )
                if error is not None:
                    errors["base"] = error

            if not errors:
                data_updates: dict[str, Any] = {}
                if new_api_key and new_api_key != entry.data[CONF_API_KEY]:
                    data_updates[CONF_API_KEY] = new_api_key

                existing_issue_date = parse_issue_date(
                    entry.data.get(CONF_API_KEY_DATE)
                )
                existing_issue_date_iso = (
                    existing_issue_date.isoformat() if existing_issue_date else None
                )
                issue_date_iso: str | None

                if new_api_key and new_api_key != entry.data[CONF_API_KEY]:
                    # A new key starts a new validity period. Use the supplied
                    # date, defaulting to today when it was omitted or cleared.
                    issue_date_iso = (
                        issue_date.isoformat() if issue_date else today.isoformat()
                    )
                elif issue_date is not None:
                    issue_date_iso = issue_date.isoformat()
                else:
                    issue_date_iso = existing_issue_date_iso

                if reminder_enabled and not issue_date_iso:
                    issue_date_iso = today.isoformat()

                if issue_date_iso and issue_date_iso != existing_issue_date_iso:
                    data_updates[CONF_API_KEY_DATE] = issue_date_iso

                new_options = {
                    **entry.options,
                    CONF_RADAR_UPDATES: user_input[CONF_RADAR_UPDATES],
                    CONF_STATION_UPDATES: user_input[CONF_STATION_UPDATES],
                    CONF_API_KEY_REMINDER: reminder_enabled,
                }
                update_kwargs: dict[str, Any] = {"options": new_options}
                if data_updates:
                    update_kwargs["data"] = {**entry.data, **data_updates}
                self.hass.config_entries.async_update_entry(entry, **update_kwargs)
                if not entry.update_listeners:
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_create_entry(title="", data=new_options)

        schema = probatio.Schema(
            {
                probatio.Optional(probatio.Secret(CONF_API_KEY)): str,
                probatio.Optional(CONF_API_KEY_DATE): probatio.Maybe(
                    _OptionalDateSelector()
                ),
                probatio.Required(
                    CONF_API_KEY_REMINDER,
                    default=current_options[CONF_API_KEY_REMINDER],
                ): bool,
                probatio.Required(
                    CONF_RADAR_UPDATES,
                    default=current_options[CONF_RADAR_UPDATES],
                ): bool,
                probatio.Required(
                    CONF_STATION_UPDATES,
                    default=current_options[CONF_STATION_UPDATES],
                ): bool,
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                user_input or current_values,
            ),
            errors=errors,
            description_placeholders={
                "current_issue_date": (
                    current_issue_date.isoformat() if current_issue_date else "not set"
                ),
            },
        )


class AemetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for AEMET OpenData."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            location = user_input[CONF_LOCATION]
            latitude = location[CONF_LATITUDE]
            longitude = location[CONF_LONGITUDE]

            await self.async_set_unique_id(f"{latitude}-{longitude}")
            self._abort_if_unique_id_configured()

            error = await _async_validate_api_key(
                self.hass,
                user_input[CONF_API_KEY],
                latitude,
                longitude,
            )
            if error is not None:
                errors["base"] = error

            if not errors:
                today = dt_util.now().date()
                issue_date_input = user_input.get(CONF_API_KEY_DATE)
                issue_date = parse_issue_date(issue_date_input)
                if issue_date is None:
                    issue_date = today
                    if issue_date_input:
                        errors[CONF_API_KEY_DATE] = "invalid_date"
                elif issue_date > today:
                    errors[CONF_API_KEY_DATE] = "invalid_date"

                if not errors:
                    return self.async_create_entry(
                        title=DEFAULT_NAME,
                        data={
                            CONF_API_KEY: user_input[CONF_API_KEY],
                            CONF_API_KEY_DATE: issue_date.isoformat(),
                            CONF_LATITUDE: latitude,
                            CONF_LONGITUDE: longitude,
                        },
                        options={
                            CONF_API_KEY_REMINDER: user_input[CONF_API_KEY_REMINDER]
                        },
                    )

        schema = probatio.Schema(
            {
                probatio.Required(probatio.Secret(CONF_API_KEY)): str,
                probatio.Optional(CONF_API_KEY_REMINDER, default=False): bool,
                probatio.Optional(CONF_API_KEY_DATE, default=None): probatio.Maybe(
                    _OptionalDateSelector()
                ),
                probatio.Required(CONF_LOCATION): LocationSelector(
                    LocationSelectorConfig(radius=False)
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                user_input
                or {
                    CONF_API_KEY_DATE: dt_util.now().date().isoformat(),
                    CONF_LOCATION: {
                        CONF_LATITUDE: self.hass.config.latitude,
                        CONF_LONGITUDE: self.hass.config.longitude,
                    },
                },
            ),
            errors=errors,
            description_placeholders={"api_key_url": API_KEY_URL},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication when the API key is no longer valid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with a new API key."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            error = await _async_validate_api_key(
                self.hass,
                user_input[CONF_API_KEY],
                entry.data[CONF_LATITUDE],
                entry.data[CONF_LONGITUDE],
            )
            if error is not None:
                errors["base"] = error
            else:
                today = dt_util.now().date()
                issue_date_input = user_input.get(CONF_API_KEY_DATE)
                issue_date = parse_issue_date(issue_date_input)
                if issue_date is None:
                    issue_date = today
                    if issue_date_input:
                        errors[CONF_API_KEY_DATE] = "invalid_date"
                elif issue_date > today:
                    errors[CONF_API_KEY_DATE] = "invalid_date"

                if not errors:
                    data = {
                        **entry.data,
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_API_KEY_DATE: issue_date.isoformat(),
                    }
                    reload = not entry.update_listeners or data == entry.data
                    result = self.async_update_and_abort(entry, data=data)
                    if reload:
                        self.hass.config_entries.async_schedule_reload(entry.entry_id)
                    return result

        schema = probatio.Schema(
            {
                probatio.Required(probatio.Secret(CONF_API_KEY)): str,
                probatio.Optional(CONF_API_KEY_DATE, default=None): probatio.Maybe(
                    _OptionalDateSelector()
                ),
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                user_input or {CONF_API_KEY_DATE: dt_util.now().date().isoformat()},
            ),
            errors=errors,
            description_placeholders={"api_key_url": API_KEY_URL},
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: AemetConfigEntry,
    ) -> AemetOptionsFlow:
        """Get the options flow for this handler."""
        return AemetOptionsFlow()
