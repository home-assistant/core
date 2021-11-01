"""Config flow for Nina integration."""  # pylint: disable=R0801
from __future__ import annotations

from typing import Any

import voluptuous as vol
from pynina import ApiError, Nina

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

    async def async_step_user(  # pylint: disable=R0914,R0912
        self: ConfigFlow,
        user_input: dict[str, Any] | None = None,  # pylint: disable=E1136,C0326
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, Any] = {}  # pylint: disable=E1136

        config_entry: Any = await self.async_set_unique_id("NINA")

        if config_entry is not None:
            return self.async_abort(reason="already_configured")

        has_error: bool = False

        if len(self._all_region_codes_sorted) == 0:  # pylint: disable=R1702
            try:
                nina: Nina = Nina()

                all_region_codes: dict[str, str] = {}  # pylint: disable=E1136

                all_region_codes = await nina.getAllRegionalCodes()

                # Swap Key/Values
                all_region_codes_swaped: dict[str, str] = {}  # pylint: disable=E1136

                for key, value in all_region_codes.items():
                    if value not in all_region_codes_swaped:
                        all_region_codes_swaped[value] = key
                    else:
                        for i in range(len(all_region_codes)):
                            tmp_value: str = value + "_" + str(i)
                            if tmp_value not in all_region_codes_swaped:
                                all_region_codes_swaped[tmp_value] = key
                                break

                self._all_region_codes_sorted = dict(
                    sorted(all_region_codes_swaped.items(), key=lambda ele: ele[1])
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

            await self.async_set_unique_id("NINA")
            return self.async_create_entry(title="NINA", data=config)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REGIONS): cv.multi_select(
                        self._all_region_codes_sorted
                    ),
                    vol.Required(CONF_MESSAGE_SLOTS, default=5): cv.positive_int,
                    vol.Required(CONF_FILTER_CORONA, default=True): cv.boolean,
                }
            ),
            errors=errors,
        )
