"""Config flow for Tankerkoenig."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiotankerkoenig import (
    GasType,
    Sort,
    Station,
    Tankerkoenig,
    TankerkoenigInvalidKeyError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
    CONF_SHOW_ON_MAP,
    UnitOfLength,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    LocationSelector,
    NumberSelector,
    NumberSelectorConfig,
)

from .const import CONF_FUEL_TYPES, CONF_STATIONS, DEFAULT_RADIUS, DOMAIN, FUEL_TYPES


async def async_get_nearby_stations(
    tankerkoenig: Tankerkoenig, data: Mapping[str, Any]
) -> list[Station]:
    """Fetch nearby stations."""
    return await tankerkoenig.nearby_stations(
        coordinates=(
            data[CONF_LOCATION][CONF_LATITUDE],
            data[CONF_LOCATION][CONF_LONGITUDE],
        ),
        radius=data[CONF_RADIUS],
        gas_type=GasType.ALL,
        sort=Sort.DISTANCE,
    )


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Init the FlowHandler."""
        super().__init__()
        self._data: dict[str, Any] = {}
        self._stations: dict[str, str] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if not user_input:
            return self._show_form_user()

        await self.async_set_unique_id(
            f"{user_input[CONF_LOCATION][CONF_LATITUDE]}_{user_input[CONF_LOCATION][CONF_LONGITUDE]}"
        )
        self._abort_if_unique_id_configured()

        tankerkoenig = Tankerkoenig(
            api_key=user_input[CONF_API_KEY],
            session=async_get_clientsession(self.hass),
        )
        try:
            stations = await async_get_nearby_stations(tankerkoenig, user_input)
        except TankerkoenigInvalidKeyError:
            return self._show_form_user(
                user_input, errors={CONF_API_KEY: "invalid_auth"}
            )

        # no stations found
        if len(stations) == 0:
            return self._show_form_user(user_input, errors={CONF_RADIUS: "no_stations"})

        for station in stations:
            self._stations[station.id] = (
                f"{station.brand} {station.street} {station.house_number} -"
                f" ({station.distance}km)"
            )

        self._data = user_input

        return await self.async_step_select_station()

    async def async_step_select_station(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step select_station of a flow initialized by the user."""
        if not user_input:
            return self.async_show_form(
                step_id="select_station",
                description_placeholders={"stations_count": str(len(self._stations))},
                data_schema=vol.Schema(
                    {vol.Required(CONF_STATIONS): cv.multi_select(self._stations)}
                ),
            )

        return self._create_entry(
            data={**self._data, **user_input},
            options={CONF_SHOW_ON_MAP: True},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Perform reauth confirm upon an API authentication error."""
        if not user_input:
            return self._show_form_reauth()

        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry
        user_input = {**entry.data, **user_input}

        tankerkoenig = Tankerkoenig(
            api_key=user_input[CONF_API_KEY],
            session=async_get_clientsession(self.hass),
        )
        try:
            await async_get_nearby_stations(tankerkoenig, user_input)
        except TankerkoenigInvalidKeyError:
            return self._show_form_reauth(user_input, {CONF_API_KEY: "invalid_auth"})

        self.hass.config_entries.async_update_entry(entry, data=user_input)
        await self.hass.config_entries.async_reload(entry.entry_id)
        return self.async_abort(reason="reauth_successful")

    def _show_form_user(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, Any] | None = None,
    ) -> FlowResult:
        if user_input is None:
            user_input = {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, "")
                    ): cv.string,
                    vol.Required(
                        CONF_API_KEY, default=user_input.get(CONF_API_KEY, "")
                    ): cv.string,
                    vol.Required(
                        CONF_FUEL_TYPES,
                        default=user_input.get(CONF_FUEL_TYPES, list(FUEL_TYPES)),
                    ): cv.multi_select(FUEL_TYPES),
                    vol.Required(
                        CONF_LOCATION,
                        default=user_input.get(
                            CONF_LOCATION,
                            {
                                "latitude": self.hass.config.latitude,
                                "longitude": self.hass.config.longitude,
                            },
                        ),
                    ): LocationSelector(),
                    vol.Required(
                        CONF_RADIUS, default=user_input.get(CONF_RADIUS, DEFAULT_RADIUS)
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1.0,
                            max=25,
                            step=0.1,
                            unit_of_measurement=UnitOfLength.KILOMETERS,
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    def _show_form_reauth(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, Any] | None = None,
    ) -> FlowResult:
        if user_input is None:
            user_input = {}
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_KEY, default=user_input.get(CONF_API_KEY, "")
                    ): cv.string,
                }
            ),
            errors=errors,
        )

    def _create_entry(
        self, data: dict[str, Any], options: dict[str, Any]
    ) -> FlowResult:
        return self.async_create_entry(
            title=data[CONF_NAME],
            data=data,
            options=options,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._stations: dict[str, str] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **self.config_entry.data,
                    CONF_STATIONS: user_input.pop(CONF_STATIONS),
                },
            )
            return self.async_create_entry(title="", data=user_input)

        tankerkoenig = Tankerkoenig(
            api_key=self.config_entry.data[CONF_API_KEY],
            session=async_get_clientsession(self.hass),
        )
        try:
            stations = await async_get_nearby_stations(
                tankerkoenig, self.config_entry.data
            )
        except TankerkoenigInvalidKeyError:
            return self.async_show_form(step_id="init", errors={"base": "invalid_auth"})

        if stations:
            for station in stations:
                self._stations[station.id] = (
                    f"{station.brand} {station.street} {station.house_number} -"
                    f" ({station.distance}km)"
                )

        # add possible extra selected stations from import
        for selected_station in self.config_entry.data[CONF_STATIONS]:
            if selected_station not in self._stations:
                self._stations[selected_station] = f"id: {selected_station}"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SHOW_ON_MAP,
                        default=self.config_entry.options[CONF_SHOW_ON_MAP],
                    ): bool,
                    vol.Required(
                        CONF_STATIONS, default=self.config_entry.data[CONF_STATIONS]
                    ): cv.multi_select(self._stations),
                }
            ),
        )
