"""UI configuration flow."""

from typing import Any

from ohme import OhmeApiClient
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)

from .const import (
    CONFIG_VERSION,
    DEFAULT_INTERVAL_ACCOUNTINFO,
    DEFAULT_INTERVAL_ADVANCED,
    DEFAULT_INTERVAL_CHARGESESSIONS,
    DEFAULT_INTERVAL_SCHEDULES,
    DOMAIN,
)

USER_SCHEMA = vol.Schema({vol.Required("email"): str, vol.Required("password"): str})


class OhmeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow."""

    VERSION = CONFIG_VERSION

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First config step."""

        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input["email"])
            self._abort_if_unique_id_configured()
            instance = OhmeApiClient(user_input["email"], user_input["password"])
            if await instance.async_refresh_session() is None:
                errors["base"] = "auth_error"
            else:
                return self.async_create_entry(
                    title=user_input["email"], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry[Any]) -> OptionsFlow:
        """Return options flow."""
        return OhmeOptionsFlow(config_entry)


class OhmeOptionsFlow(OptionsFlow):
    """Options flow."""

    def __init__(self, entry) -> None:
        """Initialize options flow and store config entry."""
        self._config_entry = entry

    async def async_step_init(self, options) -> ConfigFlowResult:
        """First step of options flow."""

        errors = {}
        # If form filled
        if options is not None:
            data: dict[str, Any] = dict(self._config_entry.data)

            # Update credentials
            if "email" in options and "password" in options:
                instance = OhmeApiClient(options["email"], options["password"])
                if await instance.async_refresh_session() is None:
                    errors["base"] = "auth_error"
                else:
                    data["email"] = options["email"]
                    data["password"] = options["password"]

            # If we have no errors, update the data array
            if len(errors) == 0:
                # Don't store email and password in options
                options.pop("email", None)
                options.pop("password", None)

                # Update data
                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=data
                )

                # Update options
                return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "email", default=self._config_entry.data["email"]
                    ): str,
                    vol.Optional("password"): str,
                    vol.Required(
                        "never_session_specific",
                        default=self._config_entry.options.get(
                            "never_session_specific", False
                        ),
                    ): bool,
                    vol.Required(
                        "never_collapse_slots",
                        default=self._config_entry.options.get(
                            "never_collapse_slots", False
                        ),
                    ): bool,
                    vol.Required(
                        "interval_chargesessions",
                        default=self._config_entry.options.get(
                            "interval_chargesessions", DEFAULT_INTERVAL_CHARGESESSIONS
                        ),
                    ): vol.All(
                        vol.Coerce(float),
                        vol.Clamp(min=DEFAULT_INTERVAL_CHARGESESSIONS),
                    ),
                    vol.Required(
                        "interval_accountinfo",
                        default=self._config_entry.options.get(
                            "interval_accountinfo", DEFAULT_INTERVAL_ACCOUNTINFO
                        ),
                    ): vol.All(
                        vol.Coerce(float), vol.Clamp(min=DEFAULT_INTERVAL_ACCOUNTINFO)
                    ),
                    vol.Required(
                        "interval_advanced",
                        default=self._config_entry.options.get(
                            "interval_advanced", DEFAULT_INTERVAL_ADVANCED
                        ),
                    ): vol.All(
                        vol.Coerce(float), vol.Clamp(min=DEFAULT_INTERVAL_ADVANCED)
                    ),
                    vol.Required(
                        "interval_schedules",
                        default=self._config_entry.options.get(
                            "interval_schedules", DEFAULT_INTERVAL_SCHEDULES
                        ),
                    ): vol.All(
                        vol.Coerce(float), vol.Clamp(min=DEFAULT_INTERVAL_SCHEDULES)
                    ),
                }
            ),
            errors=errors,
        )
