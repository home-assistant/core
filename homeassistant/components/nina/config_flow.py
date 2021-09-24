"""Config flow for Nina integration."""
from __future__ import annotations

from typing import Any

from pynina import ApiError, Nina
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import _LOGGER, CONF_FILTER_CORONA, CONF_MESSAGE_SLOTS, CONF_REGIONS, DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NINA."""

    VERSION: int = 1

    def __init__(self) -> None:
        """Initialize."""
        super().__init__()
        self._allRegionCodesSorted: dict[str, str] = {}

    async def async_step_user(
        self: ConfigFlow, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, Any] = {}

        config_entry: Any = await self.async_set_unique_id("NINA")

        if config_entry is not None:
            return self.async_abort(reason="already_configured")

        hasError: bool = False

        if len(self._allRegionCodesSorted) == 0:
            try:
                nina: Nina = Nina()

                allRegionCodes: dict[str, str] = {}

                allRegionCodes = await nina.getAllRegionalCodes()

                # Swap Key/Values
                allRegionCodesSwaped: dict[str, str] = {}

                for key, value in allRegionCodes.items():
                    if value not in allRegionCodesSwaped:
                        allRegionCodesSwaped[value] = key
                    else:
                        for i in range(100):
                            tmpValue: str = value + "_" + str(i)
                            if tmpValue not in allRegionCodesSwaped:
                                allRegionCodesSwaped[tmpValue] = key
                                break

                self._allRegionCodesSorted = {
                    key: val
                    for key, val in sorted(
                        allRegionCodesSwaped.items(), key=lambda ele: ele[1]
                    )
                }

            except ApiError as err:
                _LOGGER.warning(f"NINA setup error: {err}")
                errors["base"] = "cannot_connect"
                hasError = True
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception(f"Unexpected exception: {err}")
                errors["base"] = "unknown"
                hasError = True

        if user_input is not None and not hasError:
            config: dict[str, Any] = user_input

            tmp: dict[str, Any] = {}

            for reg in config[CONF_REGIONS]:
                tmp[self._allRegionCodesSorted[reg]] = reg.split("_", 1)[0]

            compact: dict[str, Any] = {}

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
                        self._allRegionCodesSorted
                    ),
                    vol.Required(CONF_MESSAGE_SLOTS, default=5): cv.positive_int,
                    vol.Required(CONF_FILTER_CORONA, default=True): cv.boolean,
                }
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
