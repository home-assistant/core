"""Config flow for meteoswiss integration."""

import functools
from typing import Any

import pandas as pd
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN, LOCATION_NAME, POSTAL_CODE, POSTAL_CODE_ADDITIONAL_NUMBER


class MeteoSwissConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for meteoswiss."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize ConfigFlow."""
        super().__init__()
        self._postal_code_mapping: dict[str, tuple[int, int]] = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        return self.async_show_menu(
            step_id="user",
            menu_options={
                "weather_forecast": "Weather Forecast",
            },
        )

    async def async_step_weather_forecast(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the setup of a weather forecast device."""
        errors: dict[str, str] = {}

        if self._postal_code_mapping is None:
            df = await self.hass.async_add_executor_job(
                functools.partial(
                    pd.read_csv,
                    "https://data.geo.admin.ch/ch.swisstopo-vd.ortschaftenverzeichnis_plz/ortschaftenverzeichnis_plz/ortschaftenverzeichnis_plz_2056.csv.zip",
                    header=0,
                    sep=";",
                )
            )
            df = df[["Ortschaftsname", "PLZ", "Zusatzziffer"]].drop_duplicates()
            # TODO: split the post code and location number: also on the Meteoswiss client.
            self._postal_code_mapping = {
                f'{r["PLZ"]}, {r["Ortschaftsname"]}': (r["PLZ"], r["Zusatzziffer"])
                for _, r in df.iterrows()
            }

        if user_input is not None:
            postal_code, additional_number = self._postal_code_mapping.get(
                user_input[POSTAL_CODE]
            )
            if postal_code is None:
                errors["base"] = "postal_code_not_found"
            else:
                return self.async_create_entry(
                    title=user_input[LOCATION_NAME],
                    data={
                        LOCATION_NAME: user_input[LOCATION_NAME],
                        POSTAL_CODE: postal_code,
                        POSTAL_CODE_ADDITIONAL_NUMBER: additional_number,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(LOCATION_NAME, default="Home"): str,
                vol.Required(POSTAL_CODE): SelectSelector(
                    SelectSelectorConfig(
                        options=list(self._postal_code_mapping.keys()),
                        mode=SelectSelectorMode.DROPDOWN,
                        sort=True,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="weather_forecast", data_schema=data_schema, errors=errors
        )
