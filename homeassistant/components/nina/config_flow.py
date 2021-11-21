"""Config flow for Nina integration."""  # pylint: disable=R0801
from __future__ import annotations

from typing import Any

import voluptuous as vol  # pylint: disable=E0401
from pynina import ApiError, Nina  # pylint: disable=E0401

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (  # pylint: disable=W0611
    _LOGGER,
    CONF_FILTER_CORONA,
    CONF_MESSAGE_SLOTS,
    CONF_REGIONS,
    DOMAIN,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NINA."""

    VERSION: int = 1

    def __init__(self) -> None:
        """Initialize."""
        super().__init__()
        self._all_region_codes_sorted: dict[str, str] = {}  # pylint: disable=E1136
        self.regions_a: dict[str, Any] = {}  # pylint: disable=E1136
        self.regions_b: dict[str, Any] = {}  # pylint: disable=E1136
        self.regions_c: dict[str, Any] = {}  # pylint: disable=E1136
        self.regions_d: dict[str, Any] = {}  # pylint: disable=E1136
        self.regions_e: dict[str, Any] = {}  # pylint: disable=E1136
        self.regions_f: dict[str, Any] = {}  # pylint: disable=E1136

    async def async_step_user(  # pylint: disable=R0914,R0912
        self: ConfigFlow,  # pylint: disable=C0330
        user_input: dict[str, Any] | None = None,  # pylint: disable=E1136,C0326,C0330
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, Any] = {}  # pylint: disable=E1136

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        has_error: bool = False

        if len(self._all_region_codes_sorted) == 0:  # pylint: disable=R1702
            try:
                nina: Nina = Nina()

                self._all_region_codes_sorted = self.swap_key_value(
                    await nina.getAllRegionalCodes()
                )

            except ApiError as err:
                _LOGGER.warning("NINA setup error: %s", err)
                errors["base"] = "cannot_connect"
                has_error = True
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "unknown"
                has_error = True

        if user_input is not None and not has_error:
            config: dict[str, Any] = user_input  # pylint: disable=E1136

            config[CONF_REGIONS] = []

            if CONF_REGIONS + "1" in user_input:
                config[CONF_REGIONS] += user_input[CONF_REGIONS + "1"]
            if CONF_REGIONS + "2" in user_input:
                config[CONF_REGIONS] += user_input[CONF_REGIONS + "2"]
            if CONF_REGIONS + "3" in user_input:
                config[CONF_REGIONS] += user_input[CONF_REGIONS + "3"]
            if CONF_REGIONS + "4" in user_input:
                config[CONF_REGIONS] += user_input[CONF_REGIONS + "4"]
            if CONF_REGIONS + "5" in user_input:
                config[CONF_REGIONS] += user_input[CONF_REGIONS + "5"]
            if CONF_REGIONS + "6" in user_input:
                config[CONF_REGIONS] += user_input[CONF_REGIONS + "6"]

            if len(config[CONF_REGIONS]) > 0:
                tmp: dict[str, Any] = {}  # pylint: disable=E1136

                for reg in config[CONF_REGIONS]:
                    tmp[self._all_region_codes_sorted[reg]] = reg.split("_", 1)[0]

                compact: dict[str, Any] = {}  # pylint: disable=E1136

                for key, val in tmp.items():
                    if val in compact:
                        compact[val] = f"{compact[val]} + {key}"
                        break
                    compact[val] = key

                config[CONF_REGIONS] = compact

                return self.async_create_entry(title="NINA", data=config)

            errors["base"] = "no_selection"

        self.split_regions()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_REGIONS + "1"): cv.multi_select(self.regions_a),
                    vol.Optional(CONF_REGIONS + "2"): cv.multi_select(self.regions_b),
                    vol.Optional(CONF_REGIONS + "3"): cv.multi_select(self.regions_c),
                    vol.Optional(CONF_REGIONS + "4"): cv.multi_select(self.regions_d),
                    vol.Optional(CONF_REGIONS + "5"): cv.multi_select(self.regions_e),
                    vol.Optional(CONF_REGIONS + "6"): cv.multi_select(self.regions_f),
                    vol.Required(CONF_MESSAGE_SLOTS, default=5): vol.All(
                        int, vol.Range(min=1, max=20)
                    ),
                    vol.Required(CONF_FILTER_CORONA, default=True): cv.boolean,
                }
            ),
            errors=errors,
        )

    @staticmethod
    def swap_key_value(
        dict_to_sort: dict[str, str]  # pylint: disable=E1136,C0330
    ) -> dict[str, str]:  # pylint: disable=E1136
        """Swap keys and values in dict."""
        all_region_codes_swaped: dict[str, str] = {}  # pylint: disable=E1136

        for key, value in dict_to_sort.items():
            if value not in all_region_codes_swaped:
                all_region_codes_swaped[value] = key
            else:
                for i in range(len(dict_to_sort)):
                    tmp_value: str = value + "_" + str(i)
                    if tmp_value not in all_region_codes_swaped:
                        all_region_codes_swaped[tmp_value] = key
                        break

        return dict(sorted(all_region_codes_swaped.items(), key=lambda ele: ele[1]))

    def split_regions(self) -> None:
        """Split regions alphabetical."""
        for i, name in self._all_region_codes_sorted.items():
            if name[0] == "A" or name[0] == "B" or name[0] == "C" or name[0] == "D":
                self.regions_a[i] = name
            if name[0] == "E" or name[0] == "F" or name[0] == "G" or name[0] == "H":
                self.regions_b[i] = name
            if name[0] == "I" or name[0] == "J" or name[0] == "K" or name[0] == "L":
                self.regions_c[i] = name
            if (
                name[0] == "M"  # pylint: disable=C0330
                or name[0] == "N"  # pylint: disable=C0330
                or name[0] == "O"  # pylint: disable=C0330
                or name[0] == "P"  # pylint: disable=C0330
                or name[0] == "Q"  # pylint: disable=C0330
            ):
                self.regions_d[i] = name
            if name[0] == "R" or name[0] == "S" or name[0] == "T" or name[0] == "U":
                self.regions_e[i] = name
            if (
                name[0] == "V"  # pylint: disable=C0330
                or name[0] == "W"  # pylint: disable=C0330
                or name[0] == "X"  # pylint: disable=C0330
                or name[0] == "Y"  # pylint: disable=C0330
                or name[0] == "Z"  # pylint: disable=C0330
            ):
                self.regions_f[i] = name
