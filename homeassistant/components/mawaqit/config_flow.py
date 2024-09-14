"""Adds config flow for Mawaqit."""

import json
import logging
import os

from aiohttp.client_exceptions import ClientConnectorError
from mawaqit.consts import NoMosqueAround
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import callback

from . import mawaqit_wrapper
from .const import CONF_CALC_METHOD, CONF_UUID, DOMAIN
from .utils import (
    create_data_folder,
    read_all_mosques_NN_file,
    read_my_mosque_NN_file,
    write_all_mosques_NN_file,
    write_my_mosque_NN_file,
)

_LOGGER = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))


class MawaqitPrayerFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for MAWAQIT."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """Initialize."""
        self._errors: dict[str, str] = {}

    async def async_step_user(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""

        self._errors = {}

        lat = self.hass.config.latitude
        longi = self.hass.config.longitude

        # create data folder if does not exist
        create_data_folder()

        # if the data folder is empty, we can continue the configuration
        # otherwise, we abort the configuration because that means that the user has already configured an entry.
        if is_another_instance():
            return self.async_abort(reason="one_instance_allowed")

        if user_input is None:
            return await self._show_config_form(user_input=None)

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        # check if the user credentials are correct (valid = True) :
        try:
            valid = await mawaqit_wrapper.test_credentials(username, password)
        # if we have an error connecting to the server :
        except ClientConnectorError:
            self._errors["base"] = "cannot_connect_to_server"
            return await self._show_config_form(user_input)

        if valid:
            mawaqit_token = await mawaqit_wrapper.get_mawaqit_api_token(
                username, password
            )

            os.environ["MAWAQIT_API_KEY"] = mawaqit_token

            try:
                nearest_mosques = await mawaqit_wrapper.all_mosques_neighborhood(
                    lat, longi, token=mawaqit_token
                )
            except NoMosqueAround:
                return self.async_abort(reason="no_mosque")

            await write_all_mosques_NN_file(nearest_mosques, self.hass)

            # creation of the list of mosques to be displayed in the options
            name_servers, uuid_servers, CALC_METHODS = await read_all_mosques_NN_file(
                self.hass
            )

            file_path = f"{CURRENT_DIR}/data/mosq_list_data"

            def write():
                with open(file_path, "w+", encoding="utf-8") as text_file:
                    json.dump({"CALC_METHODS": CALC_METHODS}, text_file)

            await self.hass.async_add_executor_job(write)

            return await self.async_step_mosques()

        # (if not valid)
        self._errors["base"] = "wrong_credential"

        return await self._show_config_form(user_input)

    async def async_step_mosques(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        """Handle mosques step."""

        self._errors = {}

        lat = self.hass.config.latitude
        longi = self.hass.config.longitude

        mawaqit_token = get_mawaqit_token_from_file()

        if user_input is not None:
            name_servers, uuid_servers, CALC_METHODS = await read_all_mosques_NN_file(
                self.hass
            )

            mosque = user_input[CONF_UUID]
            index = name_servers.index(mosque)
            mosque_id = uuid_servers[index]

            nearest_mosques = await mawaqit_wrapper.all_mosques_neighborhood(
                lat, longi, token=mawaqit_token
            )

            await write_my_mosque_NN_file(nearest_mosques[index], self.hass)

            # the mosque chosen by user
            dict_calendar = await mawaqit_wrapper.fetch_prayer_times(
                mosque=mosque_id, token=mawaqit_token
            )

            def write():
                with open(
                    "{dir}/data/pray_time{name}.txt".format(dir=CURRENT_DIR, name=""),
                    "w",
                    encoding="utf-8",
                ) as f:
                    json.dump(dict_calendar, f)

            await self.hass.async_add_executor_job(write)

            title = "MAWAQIT" + " - " + nearest_mosques[index]["name"]
            data_entry = {
                CONF_API_KEY: mawaqit_token,
                CONF_UUID: mosque_id,
                CONF_LATITUDE: lat,
                CONF_LONGITUDE: longi,
            }

            return self.async_create_entry(title=title, data=data_entry)

        return await self._show_config_form2()

    async def _show_config_form(self, user_input):
        if user_input is None:
            user_input = {}
            user_input[CONF_USERNAME] = ""
            user_input[CONF_PASSWORD] = ""

        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=user_input[CONF_USERNAME]): str,
                vol.Required(CONF_PASSWORD, default=user_input[CONF_PASSWORD]): str,
            }
        )

        # Show the configuration form to edit location data.
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=self._errors,
        )

    async def _show_config_form2(self):
        """Show the configuration form to edit location data."""
        lat = self.hass.config.latitude
        longi = self.hass.config.longitude

        mawaqit_token = get_mawaqit_token_from_file()

        nearest_mosques = await mawaqit_wrapper.all_mosques_neighborhood(
            lat, longi, token=mawaqit_token
        )

        await write_all_mosques_NN_file(nearest_mosques, self.hass)

        name_servers, uuid_servers, CALC_METHODS = await read_all_mosques_NN_file(
            self.hass
        )

        return self.async_show_form(
            step_id="mosques",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UUID): vol.In(name_servers),
                }
            ),
            errors=self._errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return MawaqitPrayerOptionsFlowHandler(config_entry)


class MawaqitPrayerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Mawaqit Prayer client options."""

    def __init__(self, config_entry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            lat = self.hass.config.latitude
            longi = self.hass.config.longitude

            name_servers, uuid_servers, CALC_METHODS = await read_all_mosques_NN_file(
                self.hass
            )

            mosque = user_input[CONF_CALC_METHOD]
            index = name_servers.index(mosque)
            mosque_id = uuid_servers[index]

            mawaqit_token = get_mawaqit_token_from_file()

            try:
                nearest_mosques = await mawaqit_wrapper.all_mosques_neighborhood(
                    lat, longi, token=mawaqit_token
                )
            except NoMosqueAround as err:
                raise NoMosqueAround("No mosque around.") from err

            await write_my_mosque_NN_file(nearest_mosques[index], self.hass)

            # the mosque chosen by user
            dict_calendar = await mawaqit_wrapper.fetch_prayer_times(
                mosque=mosque_id, token=mawaqit_token
            )

            def write():
                with open(
                    "{dir}/data/pray_time{name}.txt".format(dir=CURRENT_DIR, name=""),
                    "w",
                    encoding="utf-8",
                ) as f:
                    json.dump(dict_calendar, f)

            await self.hass.async_add_executor_job(write)

            title_entry = "MAWAQIT" + " - " + nearest_mosques[index]["name"]

            data_entry = {
                CONF_API_KEY: mawaqit_token,
                CONF_UUID: mosque_id,
                CONF_LATITUDE: lat,
                CONF_LONGITUDE: longi,
            }

            self.hass.config_entries.async_update_entry(
                self.config_entry, title=title_entry, data=data_entry
            )
            # return self.config_entry
            return self.async_create_entry(title=None, data={})
            # return self.async_create_entry(title=None, data=None) #"None" is not assignable to "Mapping[str, Any]

        lat = self.hass.config.latitude
        longi = self.hass.config.longitude

        mawaqit_token = get_mawaqit_token_from_file()

        nearest_mosques = await mawaqit_wrapper.all_mosques_neighborhood(
            lat, longi, token=mawaqit_token
        )

        await write_all_mosques_NN_file(nearest_mosques, self.hass)

        name_servers, uuid_servers, CALC_METHODS = await read_all_mosques_NN_file(
            self.hass
        )

        current_mosque_data = await read_my_mosque_NN_file(self.hass)
        current_mosque = current_mosque_data["uuid"]

        try:
            index = uuid_servers.index(current_mosque)
            default_name = name_servers[index]
        except ValueError:
            default_name = "None"

        options = {
            vol.Required(
                CONF_CALC_METHOD,
                default=default_name,
            ): vol.In(name_servers)
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))


def get_mawaqit_token_from_file():
    """Retrieve the Mawaqit API token from the environment variable."""
    return os.environ.get("MAWAQIT_API_KEY", "NA")


def is_already_configured():
    """Check if the mosque configuration file already exists."""
    return os.path.isfile(f"{CURRENT_DIR}/data/my_mosque_NN.txt")


def is_another_instance() -> bool:
    """Check if another instance of the mosque configuration exists."""
    if is_already_configured():
        return True
    return False
