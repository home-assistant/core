"""Config flow for Nina integration."""
from __future__ import annotations

from typing import Any

from pynina import ApiError, Nina
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import (
    _LOGGER,
    CONF_FILTER_CORONA,
    CONF_MESSAGE_SLOTS,
    CONF_REGIONS,
    CONST_REGION_MAPPING,
    CONST_REGIONS,
    DOMAIN,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NINA."""

    VERSION: int = 1

    def __init__(self) -> None:
        """Initialize."""
        super().__init__()
        self._all_region_codes_sorted: dict[str, str] = {}
        self.regions: dict[str, dict[str, Any]] = {}

        for name in CONST_REGIONS:
            self.regions[name] = {}

    async def async_step_user(
        self: ConfigFlow,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, Any] = {}

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if not self._all_region_codes_sorted:
            nina: Nina = Nina(async_get_clientsession(self.hass))

            try:
                self._all_region_codes_sorted = self.swap_key_value(
                    await nina.getAllRegionalCodes()
                )
            except ApiError:
                errors["base"] = "cannot_connect"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", err)
                return self.async_abort(reason="unknown")

            self.split_regions()

        if user_input is not None and not errors:
            user_input[CONF_REGIONS] = []

            for group in CONST_REGIONS:
                if group_input := user_input.get(group):
                    user_input[CONF_REGIONS] += group_input

            if user_input[CONF_REGIONS]:
                tmp: dict[str, Any] = {}

                for reg in user_input[CONF_REGIONS]:
                    tmp[self._all_region_codes_sorted[reg]] = reg.split("_", 1)[0]

                compact: dict[str, Any] = {}

                for key, val in tmp.items():
                    if val in compact:
                        # Abenberg, St + Abenberger Wald
                        compact[val] = f"{compact[val]} + {key}"
                        break
                    compact[val] = key

                user_input[CONF_REGIONS] = compact

                return self.async_create_entry(title="NINA", data=user_input)

            errors["base"] = "no_selection"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    **{
                        vol.Optional(region): cv.multi_select(self.regions[region])
                        for region in CONST_REGIONS
                    },
                    vol.Required(CONF_MESSAGE_SLOTS, default=5): vol.All(
                        int, vol.Range(min=1, max=20)
                    ),
                    vol.Required(CONF_FILTER_CORONA, default=True): cv.boolean,
                }
            ),
            errors=errors,
        )

    @staticmethod
    def swap_key_value(dict_to_sort: dict[str, str]) -> dict[str, str]:
        """Swap keys and values in dict."""
        all_region_codes_swaped: dict[str, str] = {}

        for key, value in dict_to_sort.items():
            if value not in all_region_codes_swaped:
                all_region_codes_swaped[value] = key
            else:
                for i in range(len(dict_to_sort)):
                    tmp_value: str = f"{value}_{i}"
                    if tmp_value not in all_region_codes_swaped:
                        all_region_codes_swaped[tmp_value] = key
                        break

        return dict(sorted(all_region_codes_swaped.items(), key=lambda ele: ele[1]))

    def split_regions(self) -> None:
        """Split regions alphabetical."""
        for index, name in self._all_region_codes_sorted.items():
            for region_name, grouping_letters in CONST_REGION_MAPPING.items():
                if name[0] in grouping_letters:
                    self.regions[region_name][index] = name
                    break
