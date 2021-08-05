"""Config flow to configure flood monitoring gauges."""
from aioeafm import get_stations
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class UKFloodsFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a UK Environment Agency flood monitoring config flow."""

    VERSION = 1

    def __init__(self):
        """Handle a UK Floods config flow."""
        self.stations = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        errors = {}

        if user_input is not None:
            station = self.stations[user_input["station"]]
            await self.async_set_unique_id(station, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input["station"],
                data={"station": station},
            )

        session = async_get_clientsession(hass=self.hass)
        stations = await get_stations(session)

        self.stations = {}
        for station in stations:
            label = station["label"]

            # API annoyingly sometimes returns a list and some times returns a string
            # E.g. L3121 has a label of ['Scurf Dyke', 'Scurf Dyke Dyke Level']
            if isinstance(label, list):
                label = label[-1]

            self.stations[label] = station["stationReference"]

        if not self.stations:
            return self.async_abort(reason="no_stations")

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {vol.Required("station"): vol.In(sorted(self.stations))}
            ),
        )
