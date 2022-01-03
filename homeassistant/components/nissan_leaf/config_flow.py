"""Config flow for Nissan Leaf integration."""
from __future__ import annotations

from datetime import timedelta
import logging
import sys
from typing import Any, cast

from pycarwings2.pycarwings2 import CarwingsError, Session
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from . import (
    CONF_CHARGING_INTERVAL,
    CONF_CLIMATE_INTERVAL,
    CONF_FORCE_MILES,
    CONF_INTERVAL,
    CONF_PASSWORD,
    CONF_REGION,
    CONF_USERNAME,
    CONF_VALID_REGIONS,
    DEFAULT_CHARGING_INTERVAL_MINS,
    DEFAULT_CLIMATE_INTERVAL_MINS,
    DEFAULT_INTERVAL_MINS,
    DOMAIN,
    MIN_UPDATE_INTERVAL_MINS,
)

_LOGGER = logging.getLogger(__name__)

# CONFIG_SCHEMA = vol.Schema(
#     {
#         DOMAIN: vol.All(
#             cv.ensure_list,
#             [
#                 vol.Schema(
#                     {
#                         vol.Required(CONF_USERNAME): cv.string,
#                         vol.Required(CONF_PASSWORD): cv.string,
#                         vol.Required(CONF_REGION): vol.In(CONF_VALID_REGIONS),
#                         vol.Optional(CONF_INTERVAL, default=DEFAULT_INTERVAL): (
#                             vol.All(cv.time_period, vol.Clamp(min=MIN_UPDATE_INTERVAL))
#                         ),
#                         vol.Optional(
#                             CONF_CHARGING_INTERVAL, default=DEFAULT_CHARGING_INTERVAL
#                         ): (
#                             vol.All(cv.time_period, vol.Clamp(min=MIN_UPDATE_INTERVAL))
#                         ),
#                         vol.Optional(
#                             CONF_CLIMATE_INTERVAL, default=DEFAULT_CLIMATE_INTERVAL
#                         ): (
#                             vol.All(cv.time_period, vol.Clamp(min=MIN_UPDATE_INTERVAL))
#                         ),
#                         vol.Optional(CONF_FORCE_MILES, default=False): cv.boolean,
#                     }
#                 )
#             ],
#         )
#     },
#     extra=vol.ALLOW_EXTRA,
# )


async def validate_auth(
    hass: HomeAssistant, username: str, password: str, region: str
) -> str | None:
    """Test authentication with given credentials."""

    _LOGGER.debug("In validate_auth")

    try:
        _LOGGER.debug("Creating session")
        sess = Session(username, password, region)

        _LOGGER.debug("Getting leaf during validation")
        leaf = await hass.async_add_executor_job(sess.get_leaf)

        _LOGGER.debug("Leaf obtained during validation")
        _LOGGER.debug("Leaf validation leaf.vin=%s", leaf.vin)

        return cast(str, leaf.vin)
    except CarwingsError:
        _LOGGER.error(
            "An unknown error occurred while connecting to Nissan: %s",
            sys.exc_info()[0],
        )

    return None


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nissan Leaf."""

    VERSION: int = 1

    def __init__(self) -> None:
        """Initialize Nissan Leaf config flow."""
        self._import_options: dict[str, Any] = {}

    async def async_step_user(
        self: ConfigFlow,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, Any] = {}

        #         if self._async_current_entries():
        #             return self.async_abort(reason="single_instance_allowed")

        #         if not self._all_region_codes_sorted:
        #             nina: Nina = Nina(async_get_clientsession(self.hass))

        #             try:
        #                 self._all_region_codes_sorted = self.swap_key_value(
        #                     await nina.getAllRegionalCodes()
        #                 )
        #             except ApiError:
        #                 errors["base"] = "cannot_connect"
        #             except Exception as err:  # pylint: disable=broad-except
        #                 _LOGGER.exception("Unexpected exception: %s", err)
        #                 return self.async_abort(reason="unknown")

        #             self.split_regions()

        _LOGGER.debug("In async_step_user")  # FIXME: Remove after debugging

        if user_input is not None:
            # Validate User input
            _LOGGER.debug("username=%s", user_input[CONF_USERNAME])
            _LOGGER.debug("password=%s", user_input[CONF_PASSWORD])
            _LOGGER.debug("region=%s", user_input[CONF_REGION])
            try:
                _LOGGER.debug("About to call validate_auth")
                vin = await validate_auth(
                    self.hass,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_REGION],
                )
                _LOGGER.debug("vin=%s", vin)
            except ValueError:
                # FIXME: Remove after debugging
                _LOGGER.debug("Could not validate correctly")
                errors["base"] = "auth"

            # FIXME: Fail if vin is None

            await self.async_set_unique_id(vin)
            self._abort_if_unique_id_configured()

            if not errors:

                _LOGGER.debug(
                    "Calling async_create_entry"
                )  # FIXME: Remove after debugging

                return self.async_create_entry(
                    title="nissan_leaf", data=user_input, options=self._import_options
                )

        _LOGGER.debug("Starting self.async_show_form")  # FIXME: Remove after debugging

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Required(CONF_REGION): vol.In(CONF_VALID_REGIONS),
                },
            ),
            errors=errors,
        )

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Handle import."""
        _LOGGER.debug("In async_step_import")  # FIXME: Remove after debugging

        user_input = {
            CONF_USERNAME: import_config[CONF_USERNAME],
            CONF_PASSWORD: import_config[CONF_PASSWORD],
            CONF_REGION: import_config[CONF_REGION],
        }

        # Convert YAML timedeltas into integer minutes because we can't serialise timedeltas
        self._import_options[CONF_INTERVAL] = (
            import_config.get(
                CONF_INTERVAL, timedelta(minutes=DEFAULT_INTERVAL_MINS)
            ).total_seconds()
            / 60
        )
        _LOGGER.debug(
            "self._import_options[conf_interval]=%s",
            self._import_options[CONF_INTERVAL],
        )

        self._import_options[CONF_CHARGING_INTERVAL] = (
            import_config.get(
                CONF_CHARGING_INTERVAL,
                timedelta(minutes=DEFAULT_CHARGING_INTERVAL_MINS),
            ).total_seconds()
            / 60
        )
        self._import_options[CONF_CLIMATE_INTERVAL] = (
            import_config.get(
                CONF_CLIMATE_INTERVAL, timedelta(minutes=DEFAULT_CLIMATE_INTERVAL_MINS)
            ).total_seconds()
            / 60
        )
        self._import_options[CONF_FORCE_MILES] = import_config.get(
            CONF_FORCE_MILES, False
        )

        _LOGGER.debug("Imported user_input=%s", user_input)
        _LOGGER.debug("Imported self._import_options=%s", self._import_options)

        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Define the config flow to handle options."""
        return NissanLeafOptionsFlowHandler(config_entry)


class NissanLeafOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an Nissan Leaf options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_INTERVAL, DEFAULT_INTERVAL_MINS
                ),
            ): (vol.All(vol.Coerce(int), vol.Clamp(min=MIN_UPDATE_INTERVAL_MINS))),
            vol.Optional(
                CONF_CHARGING_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_CHARGING_INTERVAL, DEFAULT_CHARGING_INTERVAL_MINS
                ),
            ): (vol.All(vol.Coerce(int), vol.Clamp(min=MIN_UPDATE_INTERVAL_MINS))),
            vol.Optional(
                CONF_CLIMATE_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_CLIMATE_INTERVAL, DEFAULT_CLIMATE_INTERVAL_MINS
                ),
            ): (vol.All(vol.Coerce(int), vol.Clamp(min=MIN_UPDATE_INTERVAL_MINS))),
            vol.Optional(
                CONF_FORCE_MILES,
                default=self.config_entry.options.get(CONF_FORCE_MILES, False),
            ): cv.boolean,
        }
        _LOGGER.debug("New Options=%s", options)

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))


# class UpnpOptionsFlowHandler(config_entries.OptionsFlow):
#     """Handle a UPnP options flow."""

#     def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
#         """Initialize."""
#         self.config_entry = config_entry

#     async def async_step_init(self, user_input: Mapping = None) -> None:
#         """Manage the options."""
#         if user_input is not None:
#             coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]
#             update_interval_sec = user_input.get(
#                 CONFIG_ENTRY_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
#             )
#             update_interval = timedelta(seconds=update_interval_sec)
#             LOGGER.debug("Updating coordinator, update_interval: %s", update_interval)
#             coordinator.update_interval = update_interval
#             return self.async_create_entry(title="", data=user_input)

#         scan_interval = self.config_entry.options.get(
#             CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
#         )
#         return self.async_show_form(
#             step_id="init",
#             data_schema=vol.Schema(
#                 {
#                     vol.Optional(
#                         CONF_SCAN_INTERVAL,
#                         default=scan_interval,
#                     ): vol.All(vol.Coerce(int), vol.Range(min=30)),
#                 }
#             ),
#         )
