"""Config flow for Nissan Leaf integration."""
from __future__ import annotations

import logging
import sys
from typing import Any, cast

from pycarwings2.pycarwings2 import CarwingsError, Session
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

# from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from . import (  # _LOGGER,; CONF_FILTER_CORONA,; CONF_MESSAGE_SLOTS,; CONF_REGIONS,; CONST_REGION_MAPPING,; CONST_REGIONS,
    CONF_CHARGING_INTERVAL,
    CONF_CLIMATE_INTERVAL,
    CONF_FORCE_MILES,
    CONF_INTERVAL,
    CONF_PASSWORD,
    CONF_REGION,
    CONF_USERNAME,
    CONF_VALID_REGIONS,
    DEFAULT_CHARGING_INTERVAL,
    DEFAULT_CLIMATE_INTERVAL,
    DEFAULT_INTERVAL,
    DOMAIN,
    MIN_UPDATE_INTERVAL,
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

    try:
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

        if user_input is not None:
            # Validate User input
            try:
                vin = await validate_auth(
                    self.hass,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_REGION],
                )
                _LOGGER.debug("vin=%s", vin)
            except ValueError:
                errors["base"] = "auth"

            # FIXME: Fail if vin is None

            await self.async_set_unique_id(vin)
            self._abort_if_unique_id_configured()

            if not errors:

                return self.async_create_entry(title="nissan_leaf", data=user_input)

        #             for group in CONST_REGIONS:
        #                 if group_input := user_input.get(group):
        #                     user_input[CONF_REGIONS] += group_input

        #             if user_input[CONF_REGIONS]:
        #                 tmp: dict[str, Any] = {}

        #                 for reg in user_input[CONF_REGIONS]:
        #                     tmp[self._all_region_codes_sorted[reg]] = reg.split("_", 1)[0]

        #                 compact: dict[str, Any] = {}

        #                 for key, val in tmp.items():
        #                     if val in compact:
        #                         # Abenberg, St + Abenberger Wald
        #                         compact[val] = f"{compact[val]} + {key}"
        #                         break
        #                     compact[val] = key

        #                 user_input[CONF_REGIONS] = compact

        #                 return self.async_create_entry(title="NINA", data=user_input)

        #             errors["base"] = "no_selection"

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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Define the config flow to handle options."""
        return NissanLeafOptionsFlowHandler(config_entry)


#     @staticmethod
#     def swap_key_value(dict_to_sort: dict[str, str]) -> dict[str, str]:
#         """Swap keys and values in dict."""
#         all_region_codes_swaped: dict[str, str] = {}

#         for key, value in dict_to_sort.items():
#             if value not in all_region_codes_swaped:
#                 all_region_codes_swaped[value] = key
#             else:
#                 for i in range(len(dict_to_sort)):
#                     tmp_value: str = f"{value}_{i}"
#                     if tmp_value not in all_region_codes_swaped:
#                         all_region_codes_swaped[tmp_value] = key
#                         break

#         return dict(sorted(all_region_codes_swaped.items(), key=lambda ele: ele[1]))

#     def split_regions(self) -> None:
#         """Split regions alphabetical."""
#         for index, name in self._all_region_codes_sorted.items():
#             for region_name, grouping_letters in CONST_REGION_MAPPING.items():
#                 if name[0] in grouping_letters:
#                     self.regions[region_name][index] = name
#                     break


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

        # FIXME: Set default values here from the current settings if they exist
        options = {
            vol.Optional(CONF_INTERVAL, default=DEFAULT_INTERVAL): (
                vol.All(vol.Coerce(int), vol.Clamp(min=MIN_UPDATE_INTERVAL))
            ),
            vol.Optional(CONF_CHARGING_INTERVAL, default=DEFAULT_CHARGING_INTERVAL): (
                vol.All(vol.Coerce(int), vol.Clamp(min=MIN_UPDATE_INTERVAL))
            ),
            vol.Optional(CONF_CLIMATE_INTERVAL, default=DEFAULT_CLIMATE_INTERVAL): (
                vol.All(vol.Coerce(int), vol.Clamp(min=MIN_UPDATE_INTERVAL))
            ),
            vol.Optional(CONF_FORCE_MILES, default=False): cv.boolean,
        }

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
