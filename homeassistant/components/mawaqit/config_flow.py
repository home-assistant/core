"""Adds config flow for Mawaqit."""

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from . import mawaqit_wrapper, utils
from .const import (
    CONF_CALC_METHOD,
    CONF_UUID,
    DOMAIN,
    MAWAQIT_STORAGE_KEY,
    MAWAQIT_STORAGE_VERSION,
)
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
        self.store: Store | None = None

    async def async_step_user(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""

        self._errors = {}

        if self.store is None:
            self.store = Store(self.hass, MAWAQIT_STORAGE_VERSION, MAWAQIT_STORAGE_KEY)

        lat = self.hass.config.latitude
        longi = self.hass.config.longitude

        # create data folder if does not exist
        create_data_folder()

        # if the data folder is empty, we can continue the configuration
        # otherwise, we abort the configuration because that means that the user has already configured an entry.
        if await is_another_instance(self.hass, self.store):
            # return self.async_abort(reason="one_instance_allowed")
            return await self._show_keep_or_reset_form()

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

            await utils.write_mawaqit_token(self.hass, self.store, mawaqit_token)
            # os.environ["MAWAQIT_API_KEY"] = mawaqit_token

            try:
                nearest_mosques = await mawaqit_wrapper.all_mosques_neighborhood(
                    lat, longi, token=mawaqit_token
                )
            except NoMosqueAround:
                return self.async_abort(reason="no_mosque")

            await write_all_mosques_NN_file(nearest_mosques, self.store)

            # creation of the list of mosques to be displayed in the options
            name_servers, uuid_servers, CALC_METHODS = await read_all_mosques_NN_file(
                self.store
            )

            await utils.async_write_in_data(
                self.hass, CURRENT_DIR, "mosq_list_data", {"CALC_METHODS": CALC_METHODS}
            )  # TODO deprecate this line and put instead  "await utils.write_mosq_list_data({"CALC_METHODS": CALC_METHODS}, self.store)" # pylint: disable=fixme

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

        mawaqit_token = await utils.read_mawaqit_token(self.hass, self.store)

        if user_input is not None:
            name_servers, uuid_servers, CALC_METHODS = await read_all_mosques_NN_file(
                self.store
            )

            mosque = user_input[CONF_UUID]
            index = name_servers.index(mosque)
            mosque_id = uuid_servers[index]

            nearest_mosques = await mawaqit_wrapper.all_mosques_neighborhood(
                lat, longi, token=mawaqit_token
            )

            await write_my_mosque_NN_file(nearest_mosques[index], self.store)

            await utils.update_my_mosque_data_files(
                self.hass,
                CURRENT_DIR,
                self.store,
                mosque_id=mosque_id,
                token=mawaqit_token,
            )

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

        mawaqit_token = await utils.read_mawaqit_token(self.hass, self.store)

        nearest_mosques = await mawaqit_wrapper.all_mosques_neighborhood(
            lat, longi, token=mawaqit_token
        )

        await write_all_mosques_NN_file(nearest_mosques, self.store)

        name_servers, uuid_servers, CALC_METHODS = await read_all_mosques_NN_file(
            self.store
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

    async def _show_keep_or_reset_form(self):
        """Show form to ask the user if they want to keep current data or reset."""
        options = {vol.Required("choice", default="keep"): vol.In(["keep", "reset"])}

        return self.async_show_form(
            step_id="keep_or_reset",
            data_schema=vol.Schema(options),
            errors=self._errors,
        )

    async def async_step_keep_or_reset(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        """Handle the user's choice to keep current data or reset."""
        if user_input is None:
            return await self._show_keep_or_reset_form()

        choice = user_input["choice"]

        if choice == "keep":
            return self.async_abort(reason="configuration_kept")
        if choice == "reset":
            # Clear existing data and restart the configuration process
            await self.async_clear_data()
            return await self.async_step_user()
        return await self._show_keep_or_reset_form()

    async def async_clear_data(self):
        """Clear all data from the store and folders."""

        # Remove all config entries
        entries = self.hass.config_entries.async_entries(DOMAIN)
        for entry in entries:
            if entry.domain == DOMAIN:
                await self.hass.config_entries.async_remove(entry.entry_id)

        await self.store.async_remove()  # Remove the existing data in the store

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
        """Initialize the options flow handler."""
        self.config_entry = config_entry
        self.store: Store | None = None
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Manage options."""

        self.store = Store(self.hass, MAWAQIT_STORAGE_VERSION, MAWAQIT_STORAGE_KEY)

        if user_input is not None:
            lat = self.hass.config.latitude
            longi = self.hass.config.longitude

            name_servers, uuid_servers, CALC_METHODS = await read_all_mosques_NN_file(
                self.store
            )

            mosque = user_input[CONF_CALC_METHOD]
            index = name_servers.index(mosque)
            mosque_id = uuid_servers[index]

            mawaqit_token = await utils.read_mawaqit_token(self.hass, self.store)

            try:
                nearest_mosques = await mawaqit_wrapper.all_mosques_neighborhood(
                    lat, longi, token=mawaqit_token
                )
            except NoMosqueAround as err:
                raise NoMosqueAround("No mosque around.") from err

            await write_my_mosque_NN_file(nearest_mosques[index], self.store)

            await utils.update_my_mosque_data_files(
                self.hass,
                CURRENT_DIR,
                self.store,
                mosque_id=mosque_id,
                token=mawaqit_token,
            )

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

        mawaqit_token = await utils.read_mawaqit_token(self.hass, self.store)

        nearest_mosques = await mawaqit_wrapper.all_mosques_neighborhood(
            lat, longi, token=mawaqit_token
        )

        await write_all_mosques_NN_file(nearest_mosques, self.store)

        name_servers, uuid_servers, CALC_METHODS = await read_all_mosques_NN_file(
            self.store
        )

        current_mosque_data = await read_my_mosque_NN_file(self.store)
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


# def get_mawaqit_token_from_file(hass: HomeAssistant, store: Store):
#     """Retrieve the Mawaqit API token from the environment variable."""
#     return await utils.read_mawaqit_token(hass, store)


async def is_already_configured(hass: HomeAssistant, store: Store) -> bool:
    """Check if the mosque configuration file already exists."""
    return await utils.read_my_mosque_NN_file(store) is not None
    # return os.path.isfile(f"{CURRENT_DIR}/data/my_mosque_NN.txt")


async def is_another_instance(hass: HomeAssistant, store: Store) -> bool:
    """Check if another instance of the mosque configuration exists."""
    return await is_already_configured(hass, store)
