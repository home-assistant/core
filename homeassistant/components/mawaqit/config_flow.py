"""Adds config flow for Mawaqit."""

import logging
from typing import Any

from aiohttp.client_exceptions import ClientConnectorError
from mawaqit.consts import NoMosqueAround, NoMosqueFound
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.storage import Store

from . import mawaqit_wrapper, utils
from .const import (
    CANNOT_CONNECT_TO_SERVER,
    CONF_CALC_METHOD,
    CONF_SEARCH,
    CONF_TYPE_SEARCH,
    CONF_TYPE_SEARCH_COORDINATES,
    CONF_TYPE_SEARCH_KEYWORD,
    CONF_TYPE_SEARCH_TRANSLATION_KEY,
    CONF_UUID,
    DOMAIN,
    MAWAQIT_STORAGE_KEY,
    MAWAQIT_STORAGE_VERSION,
    NO_MOSQUE_FOUND_KEYWORD,
    WRONG_CREDENTIAL,
)

_LOGGER = logging.getLogger(__name__)


class MawaqitPrayerFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for MAWAQIT."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self.store: Store | None = None
        self.previous_keyword_search: str = ""
        self.mosques: list[Any] = []
        self.token = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""

        errors: dict[str, str] = {}
        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        if self.store is None:
            self.store = Store(self.hass, MAWAQIT_STORAGE_VERSION, MAWAQIT_STORAGE_KEY)

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=schema,
                errors=errors,
            )

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        # check if the user credentials are correct (valid = True) :
        try:
            valid = await mawaqit_wrapper.test_credentials(username, password)
        # if we have an error connecting to the server :
        except ClientConnectorError:
            errors["base"] = CANNOT_CONNECT_TO_SERVER
            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors=errors,
            )

        if valid:
            mawaqit_token = await mawaqit_wrapper.get_mawaqit_api_token(
                username, password
            )
            self.token = mawaqit_token

            return await self.async_step_search_method()

        errors["base"] = WRONG_CREDENTIAL

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_mosques_coordinates(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        """Handle mosques step."""

        errors: dict[str, str] = {}

        lat = self.hass.config.latitude
        longi = self.hass.config.longitude

        if user_input is not None:
            title, data_entry = await utils.async_save_mosque(
                user_input[CONF_UUID],
                self.mosques,
                self.token,
                lat,
                longi,
            )
            return self.async_create_entry(title=title, data=data_entry)

        self.mosques = await mawaqit_wrapper.all_mosques_neighborhood(
            lat, longi, token=self.token
        )

        name_servers, uuid_servers, CALC_METHODS = utils.parse_mosque_data(self.mosques)

        return self.async_show_form(
            step_id="mosques_coordinates",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UUID): vol.In(name_servers),
                }
            ),
            errors=errors,
        )

    async def async_step_search_method(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        """Handle the user's choice of search method."""
        errors: dict[str, str] = {}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TYPE_SEARCH, default=CONF_TYPE_SEARCH_COORDINATES
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            CONF_TYPE_SEARCH_COORDINATES,
                            CONF_TYPE_SEARCH_KEYWORD,
                        ],
                        translation_key=CONF_TYPE_SEARCH_TRANSLATION_KEY,
                    ),
                ),
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="search_method",
                data_schema=schema,
                errors=errors,
            )

        search_method = user_input[CONF_TYPE_SEARCH]

        if search_method == CONF_TYPE_SEARCH_COORDINATES:
            lat = self.hass.config.latitude
            longi = self.hass.config.longitude

            self.mosques = []
            try:
                self.mosques = await mawaqit_wrapper.all_mosques_neighborhood(
                    lat, longi, token=self.token
                )
            except NoMosqueAround:
                return self.async_abort(reason="no_mosque")

            # creation of the list of mosques to be displayed in the options
            name_servers, uuid_servers, CALC_METHODS = utils.parse_mosque_data(
                self.mosques
            )

            return await self.async_step_mosques_coordinates()

            # or return _show_config_form2
        if search_method == CONF_TYPE_SEARCH_KEYWORD:
            return await self.async_step_keyword_search()

        return self.async_show_form(
            step_id="search_method",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_keyword_search(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        """Handle the keyword search."""
        errors: dict[str, str] = {}
        option = {
            vol.Required(CONF_SEARCH): str,
        }

        if user_input is not None:
            if CONF_SEARCH in user_input:
                keyword = user_input[CONF_SEARCH]

                if keyword == self.previous_keyword_search:
                    # if the form is submitted with the same keyword as the previous one, we check if the user has selected a mosque
                    if CONF_UUID in user_input and (user_input[CONF_UUID] is not None):
                        title, data_entry = await utils.async_save_mosque(
                            user_input[CONF_UUID],
                            self.mosques,
                            mawaqit_token=self.token,
                        )
                        return self.async_create_entry(title=title, data=data_entry)
                else:
                    self.previous_keyword_search = keyword

                try:
                    self.mosques = await mawaqit_wrapper.all_mosques_by_keyword(
                        search_keyword=keyword, token=self.token
                    )
                except NoMosqueFound:
                    errors["base"] = NO_MOSQUE_FOUND_KEYWORD
                    return self.async_show_form(
                        step_id="keyword_search",
                        data_schema=self.add_suggested_values_to_schema(
                            vol.Schema(option), {CONF_SEARCH: user_input[CONF_SEARCH]}
                        ),
                        errors=errors,
                    )

                (
                    name_servers,
                    uuid_servers,
                    CALC_METHODS,
                ) = utils.parse_mosque_data(
                    self.mosques
                )  # would it be better to add the address of the mosque ?

                return self.async_show_form(
                    step_id="keyword_search",
                    data_schema=self.add_suggested_values_to_schema(
                        vol.Schema(
                            {
                                **option,
                                vol.Required(
                                    CONF_UUID,
                                    default=name_servers[0],
                                ): vol.In(name_servers),
                            }
                        ),
                        {CONF_SEARCH: user_input[CONF_SEARCH]},
                    ),
                    errors=errors,
                )

        return self.async_show_form(
            step_id="keyword_search",
            data_schema=vol.Schema(option),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return MawaqitPrayerOptionsFlowHandler()


class MawaqitPrayerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Mawaqit Prayer client options."""

    def __init__(self) -> None:
        """Initialize the options flow handler."""
        self.store: Store | None = None
        self.mosques: list[Any] = []

    async def async_step_init(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Manage options."""

        self.store = Store(self.hass, MAWAQIT_STORAGE_VERSION, MAWAQIT_STORAGE_KEY)

        lat = self.hass.config.latitude
        longi = self.hass.config.longitude
        mawaqit_token = self.config_entry.data.get(CONF_API_KEY)

        if user_input is not None:
            title_entry, data_entry = await utils.async_save_mosque(
                user_input[CONF_CALC_METHOD],
                self.mosques,
                mawaqit_token,
                lat,
                longi,
            )

            self.hass.config_entries.async_update_entry(
                self.config_entry, title=title_entry, data=data_entry
            )
            return self.async_create_entry(title=None, data={})

        # Attempt to fetch nearby mosques, handle the NoMosqueAround exception
        try:
            self.mosques = await mawaqit_wrapper.all_mosques_neighborhood(
                lat, longi, token=mawaqit_token
            )

            name_servers, uuid_servers, CALC_METHODS = utils.parse_mosque_data(
                self.mosques
            )

            current_mosque = self.config_entry.data.get(CONF_UUID)

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

        except NoMosqueAround:
            _LOGGER.error(
                "No mosque found around your location. Please check your coordinates"
            )
            return self.async_abort(reason="no_mosque")
