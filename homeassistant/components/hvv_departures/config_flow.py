"""Config flow for HVV integration."""
import logging

from pygti.auth import GTI_DEFAULT_HOST
from pygti.exceptions import CannotConnect, InvalidAuth
from pygti.gti import GTI, Auth
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

SCHEMA_STEP_USER = vol.Schema(
    {
        vol.Required("host", default=GTI_DEFAULT_HOST): str,
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)

SCHEMA_STEP_STATION = vol.Schema({vol.Required("station"): str})

SCHEMA_STEP_OPTIONS = vol.Schema(
    {
        vol.Required("filter"): vol.In([]),
        vol.Required("offset", default=0): vol.All(int, vol.Range(min=0)),
        vol.Optional("realtime", default=True): bool,
    }
)


class GTIHub:
    """GTI Hub."""

    def __init__(self, host, username, password, session):
        """Initialize."""
        self.host = host
        self.username = username
        self.password = password

        self.gti = GTI(Auth(session, self.username, self.password, self.host))

    async def authenticate(self) -> bool:
        """Test if we can authenticate with the host."""

        return await self.gti.init()


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
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize component."""
        self.hub = None
        self.data = None
        self.stations = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                session = aiohttp_client.async_get_clientsession(self.hass)
                self.hub = GTIHub(
                    user_input["host"],
                    user_input["username"],
                    user_input["password"],
                    session,
                )

                response = await self.hub.authenticate()

                _LOGGER.debug("init gti: %r", response)

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
        """Handle the step where the user inputs his/her station."""
        errors = {}
        if user_input is not None:

            check_name = await self.hub.gti.checkName(
                {"theName": {"name": user_input["station"]}, "maxList": 20}
            )

            code = check_name.get("returnCode")
            if code == "ERROR_CN_TOO_MANY":
                errors["base"] = "cn_too_many"
            elif code == "OK":

                results = check_name.get("results")

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
        """Handle the step where the user inputs his/her station."""
        errors = {}
        if user_input is not None:
            self.data.update({"station": self.stations[user_input["station"]]})

            # get station information
            station_information = await self.hub.gti.stationInformation(
                {"station": self.data["station"]}
            )

            self.filters = {
                "{}, {}".format(x["serviceName"], x["label"]): x
                for x in dl.get("filter")
            }
            self.data.update({"stationInformation": station_information})

            title = self.data["station"]["name"]

            return self.async_create_entry(title=title, data=self.data)

        return self.async_show_form(
            step_id="station_select", data_schema=SCHEMA_STEP_STATION, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow handler."""

    def __init__(self, config_entry):
        """Initialize HVV Departures options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self.filters = []
        self.hub = None

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:

            options = {
                "filter": [self.filters[user_input["filter"]]],
                "offset": user_input["offset"],
                "realtime": user_input["realtime"],
            }

            return self.async_create_entry(title="", data=options)

        session = aiohttp_client.async_get_clientsession(self.hass)
        self.hub = GTIHub(
            self.config_entry.data["host"],
            self.config_entry.data["username"],
            self.config_entry.data["password"],
            session,
        )

        if not await self.hub.authenticate():
            raise InvalidAuth

        departure_list = await self.hub.gti.departureList(
            {
                "station": self.config_entry.data["station"],
                "time": {"date": "heute", "time": "jetzt"},
                "maxList": 5,
                "maxTimeOffset": 200,
                "useRealtime": True,
                "returnFilters": True,
            }
        )

        self.filters = dict(
            [
                ("{}, {}".format(x["serviceName"], x["label"]), x)
                for x in departure_list.get("filter")
            ]
        )

        if "filter" in self.config_entry.options:
            old_filter = "{}, {}".format(
                self.config_entry.options["filter"][0]["serviceName"],
                self.config_entry.options["filter"][0]["label"],
            )
        else:
            old_filter = None

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("filter", default=old_filter): vol.In(
                        self.filters.keys()
                    ),
                    vol.Required(
                        "offset", default=self.config_entry.options.get("offset", 0)
                    ): vol.All(int, vol.Range(min=0)),
                    vol.Optional(
                        "realtime",
                        default=self.config_entry.options.get("realtime", True),
                    ): bool,
                }
            ),
        )
