"""Config flow for HVV integration."""
import logging

from pygti.gti import GTI
import voluptuous as vol

from homeassistant import config_entries, core, exceptions

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

SCHEMA_STEP_USER = vol.Schema(
    {
        vol.Required("host", default="http://api-test.geofox.de"): str,
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)

SCHEMA_STEP_STATION = vol.Schema({vol.Required("station"): str})

SCHEMA_STEP_FINISH = vol.Schema(
    {
        vol.Required("offset", default=0): vol.All(int, vol.Range(min=0)),
        vol.Optional("realtime", default=False): bool,
    }
)


class GTIHub:
    """GTI Hub"""

    def __init__(self, host, username, password):
        """Initialize."""
        self.host = host
        self.username = username
        self.password = password

        self.gti = GTI(self.username, self.password, self.host)

    async def authenticate(self) -> bool:
        """Test if we can authenticate with the host."""

        return_code = self.gti.init().get("returnCode")
        if return_code == "OK":
            return

        raise InvalidAuth


async def validate_input(hass: core.HomeAssistant, hub: GTIHub):
    """Validate the user input allows us to connect.

    Data has the keys from SCHEMA_STEP_USER with values provided by the user.
    """

    if not await hub.authenticate():
        raise InvalidAuth

    return {"title": "HVV Departure Sensor 1"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HVV."""

    VERSION = 1
    # TODO pick one of the available connection classes in homeassistant/config_entries.py
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                self.hub = GTIHub(
                    user_input["host"], user_input["username"], user_input["password"]
                )
                info = await validate_input(self.hass, self.hub)

                self.data = user_input

                return self.async_show_form(
                    step_id="station", data_schema=SCHEMA_STEP_STATION, errors=errors
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=SCHEMA_STEP_USER, errors=errors
        )

    async def async_step_station(self, user_input=None):
        """Handle the step where the user inputs his/her station"""
        errors = {}
        if user_input is not None:

            cn = self.hub.gti.checkName(
                {"theName": {"name": user_input["station"]}, "maxList": 20}
            )

            code = cn.get("returnCode")
            if code == "ERROR_CN_TOO_MANY":
                errors["base"] = "cn_too_many"
            elif code == "OK":

                results = cn.get("results")

                self.stations = {
                    "{} ({})".format(x.get("name"), x.get("type")): x for x in results
                }

                schema = vol.Schema(
                    {vol.Required("station"): vol.In(list(self.stations.keys()))}
                )

                return self.async_show_form(
                    step_id="station_select", data_schema=schema, errors=errors
                )
            else:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            pass

        return self.async_show_form(
            step_id="station", data_schema=SCHEMA_STEP_STATION, errors=errors
        )

    async def async_step_station_select(self, user_input=None):
        """Handle the step where the user inputs his/her station"""
        errors = {}
        if user_input is not None:
            self.data.update({"station": self.stations[user_input["station"]]})

            # get departures to get the correct filters

            dl = self.hub.gti.departureList(
                {
                    "station": self.data["station"],
                    "time": {"date": "heute", "time": "jetzt"},
                    "maxList": 5,
                    "maxTimeOffset": 200,
                    "useRealtime": True,
                    "returnFilters": True,
                }
            )

            self.filters = {
                "{}, {}".format(x["serviceName"], x["label"]): x
                for x in dl.get("filter")
            }

            schema = vol.Schema({"filter": vol.In(self.filters.keys())})

            return self.async_show_form(
                step_id="filter", data_schema=schema, errors=errors
            )

        return self.async_show_form(
            step_id="station_select", data_schema=SCHEMA_STEP_STATION, errors=errors
        )

    async def async_step_filter(self, user_input=None):
        """Handle the step where the user inputs his/her station"""
        errors = {}
        if user_input is not None:

            self.data.update({"filter": [self.filters[user_input["filter"]]]})

            return self.async_show_form(
                step_id="finish", data_schema=SCHEMA_STEP_FINISH, errors=errors
            )

    async def async_step_finish(self, user_input=None):
        """Handle the step where the user inputs his/her station"""
        errors = {}
        if user_input is not None:

            self.data.update(user_input)

            # get station information
            si = self.hub.gti.stationInformation({"station": self.data["station"]})

            self.data.update({"stationInformation": si})

            title = self.data["station"]["name"]

            return self.async_create_entry(title=title, data=self.data)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
