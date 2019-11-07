"""Adds config flow for GIOS."""
import logging

from async_timeout import timeout
from gios import Gios, NoStationError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_STATION_ID, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


@callback
def configured_instances(hass, condition):
    """Return a set of configured GIOS instances."""
    return set(
        entry.data[condition] for entry in hass.config_entries.async_entries(DOMAIN)
    )


class GiosFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for GIOS."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        websession = async_get_clientsession(self.hass)

        if user_input is not None:
            if user_input[CONF_NAME] in configured_instances(self.hass, CONF_NAME):
                self._errors[CONF_NAME] = "name_exists"
            if user_input[CONF_STATION_ID] in configured_instances(
                self.hass, CONF_STATION_ID
            ):
                self._errors[CONF_STATION_ID] = "station_id_exists"
            station_id_valid = await self._test_station_id(
                websession, user_input["station_id"]
            )
            if station_id_valid:
                sensors_data_valid = await self._test_sensors_data(
                    websession, user_input["station_id"]
                )
                if not sensors_data_valid:
                    self._errors["base"] = "invalid_sensors_data"
            else:
                self._errors["base"] = "wrong_station_id"
            if not self._errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self._show_config_form(name=DEFAULT_NAME, station_id="")

    def _show_config_form(self, name=None, station_id=None):
        """Show the configuration form to edit data."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATION_ID, default=station_id): int,
                    vol.Optional(CONF_NAME, default=name): str,
                }
            ),
            errors=self._errors,
        )

    async def _test_station_id(self, client, station_id):
        """Return true if station_id is valid."""
        try:
            with timeout(30):
                gios = Gios(station_id, client)
                await gios.update()
        except NoStationError:
            return False
        return True

    async def _test_sensors_data(self, client, station_id):
        """Return true if sensors data is valid."""
        with timeout(30):
            gios = Gios(station_id, client)
            await gios.update()
        if gios.available:
            return True
        return False
