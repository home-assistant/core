"""Config flow for the Mawaqit integration."""

from typing import Any

from aiohttp.client_exceptions import ClientConnectorError
from mawaqit.consts import BadCredentialsException, NoMosqueAround, NoMosqueFound
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import selector

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
    KEYWORD_SEARCH_NEXT_PAGE,
    KEYWORD_SEARCH_PAGE_SIZE,
    KEYWORD_SEARCH_PREV_PAGE,
    MAWAQIT_URL,
    NO_MOSQUE_FOUND_KEYWORD,
    WRONG_CREDENTIAL,
)


class MawaqitPrayerFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for MAWAQIT."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self.previous_keyword_search: str = ""
        self.mosques: list[dict] = []
        self.token: str | None = None
        # keyword search pagination
        self.keyword_page: int = 1
        self.keyword_has_next: bool = False
        self.current_keyword: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""

        self._async_abort_entries_match()

        errors = {}
        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
                vol.Required(CONF_PASSWORD): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
            }
        )

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            try:
                valid = await mawaqit_wrapper.validate_credentials(username, password)
            except ClientConnectorError, ConnectionError, TimeoutError:
                errors["base"] = CANNOT_CONNECT_TO_SERVER
            else:
                if valid:
                    try:
                        mawaqit_token = await mawaqit_wrapper.get_mawaqit_api_token(
                            username, password
                        )
                    except ClientConnectorError, ConnectionError, TimeoutError:
                        errors["base"] = CANNOT_CONNECT_TO_SERVER
                    else:
                        if not mawaqit_token:
                            errors["base"] = CANNOT_CONNECT_TO_SERVER
                        else:
                            self.token = mawaqit_token
                            return await self.async_step_search_method()
                else:
                    errors["base"] = WRONG_CREDENTIAL

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
            description_placeholders={"mawaqit_url": MAWAQIT_URL},
        )

    async def async_step_mosques_coordinates(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        """Handle mosques step."""

        errors: dict[str, str] = {}

        lat = self.hass.config.latitude
        longi = self.hass.config.longitude

        if user_input is not None:
            title, data_entry = utils.save_mosque(
                user_input[CONF_UUID],
                self.mosques,
                self.token,
                lat,
                longi,
            )
            return self.async_create_entry(title=title, data=data_entry)

        if not self.mosques:
            try:
                neighborhood_mosques = await mawaqit_wrapper.all_mosques_neighborhood(
                    lat, longi, token=self.token
                )
                if neighborhood_mosques:
                    self.mosques = neighborhood_mosques
            except NoMosqueAround:
                return self.async_abort(reason="no_mosque")
            except (
                BadCredentialsException,
                ClientConnectorError,
                ConnectionError,
                TimeoutError,
            ):
                return self.async_abort(reason="cannot_connect")

        name_servers, _uuid_servers, _calc_methods = utils.parse_mosque_data(
            self.mosques
        )

        if not name_servers:
            return self.async_abort(reason="no_mosque")

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
                neighborhood_mosques = await mawaqit_wrapper.all_mosques_neighborhood(
                    lat, longi, token=self.token
                )
                if neighborhood_mosques:
                    self.mosques = neighborhood_mosques

            except NoMosqueAround:
                return self.async_abort(reason="no_mosque")
            except (
                BadCredentialsException,
                ClientConnectorError,
                ConnectionError,
                TimeoutError,
            ):
                return self.async_abort(reason="cannot_connect")

            return await self.async_step_mosques_coordinates()

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
        """Handle the keyword search, with paginated results."""
        errors = {}
        option = {vol.Required(CONF_SEARCH): str}

        if user_input is not None and CONF_SEARCH in user_input:
            keyword = user_input[CONF_SEARCH]
            selected_uuid = user_input.get(CONF_UUID)

            # Handle pagination sentinels
            if selected_uuid == KEYWORD_SEARCH_NEXT_PAGE:
                self.keyword_page += 1
                selected_uuid = None  # fall through to re-fetch
            elif selected_uuid == KEYWORD_SEARCH_PREV_PAGE:
                self.keyword_page = max(1, self.keyword_page - 1)
                selected_uuid = None  # fall through to re-fetch

            # Mosque selected: save and exit
            if selected_uuid is not None and keyword == self.previous_keyword_search:
                title, data_entry = utils.save_mosque(
                    selected_uuid,
                    self.mosques,
                    mawaqit_token=self.token,
                )
                return self.async_create_entry(title=title, data=data_entry)

            # New keyword: reset to page 1
            if keyword != self.previous_keyword_search:
                self.keyword_page = 1

            self.previous_keyword_search = keyword

            # Fetch the page
            try:
                mosques_found = await mawaqit_wrapper.all_mosques_by_keyword(
                    search_keyword=keyword,
                    page=self.keyword_page,
                    token=self.token,
                )
                self.mosques = mosques_found or []
            except NoMosqueFound:
                # If we navigated past the last real page, step back silently
                if self.keyword_page > 1:
                    self.keyword_page -= 1
                errors["base"] = NO_MOSQUE_FOUND_KEYWORD
                return self.async_show_form(
                    step_id="keyword_search",
                    data_schema=self.add_suggested_values_to_schema(
                        vol.Schema(option), {CONF_SEARCH: keyword}
                    ),
                    errors=errors,
                )
            except (
                BadCredentialsException,
                ClientConnectorError,
                ConnectionError,
                TimeoutError,
            ):
                errors["base"] = CANNOT_CONNECT_TO_SERVER
                return self.async_show_form(
                    step_id="keyword_search",
                    data_schema=self.add_suggested_values_to_schema(
                        vol.Schema(option), {CONF_SEARCH: keyword}
                    ),
                    errors=errors,
                )

            name_servers, _uuid_servers, _calc_methods = utils.parse_mosque_data(
                self.mosques
            )

            if not name_servers:
                if self.keyword_page > 1:
                    self.keyword_page -= 1
                errors["base"] = NO_MOSQUE_FOUND_KEYWORD
                return self.async_show_form(
                    step_id="keyword_search",
                    data_schema=self.add_suggested_values_to_schema(
                        vol.Schema(option), {CONF_SEARCH: keyword}
                    ),
                    errors=errors,
                )

            # Build navigation-aware option list
            self.keyword_has_next = len(self.mosques) >= KEYWORD_SEARCH_PAGE_SIZE

            # Build a {value: label} dict so nav sentinels get human-readable labels
            nav_options: dict[str, str] = {}
            if self.keyword_page > 1:
                nav_options[KEYWORD_SEARCH_PREV_PAGE] = (
                    f"← Previous page (page {self.keyword_page - 1})"
                )

            nav_options.update({name: name for name in name_servers})

            if self.keyword_has_next:
                nav_options[KEYWORD_SEARCH_NEXT_PAGE] = (
                    f"→ Next page (page {self.keyword_page + 1})"
                )

            return self.async_show_form(
                step_id="keyword_search",
                data_schema=self.add_suggested_values_to_schema(
                    vol.Schema(
                        {
                            **option,
                            vol.Required(CONF_UUID, default=name_servers[0]): vol.In(
                                nav_options
                            ),
                        }
                    ),
                    {CONF_SEARCH: keyword},
                ),
                errors=errors,
                description_placeholders={"page": str(self.keyword_page)},
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
        self.mosques: list[dict] = []

    async def async_step_init(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Manage options."""

        lat = self.hass.config.latitude
        longi = self.hass.config.longitude
        mawaqit_token = self.config_entry.data.get(CONF_API_KEY)

        if user_input is not None:
            title_entry, data_entry = utils.save_mosque(
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

        try:
            neighborhood_mosques = await mawaqit_wrapper.all_mosques_neighborhood(
                lat, longi, token=mawaqit_token
            )
            if neighborhood_mosques:
                self.mosques = neighborhood_mosques
        except NoMosqueAround:
            return self.async_abort(reason="no_mosque")
        except (
            BadCredentialsException,
            ClientConnectorError,
            ConnectionError,
            TimeoutError,
        ):
            return self.async_abort(reason="cannot_connect")

        name_servers, uuid_servers, _calc_methods = utils.parse_mosque_data(
            self.mosques
        )

        if not name_servers:
            return self.async_abort(reason="no_mosque")

        current_mosque = self.config_entry.data.get(CONF_UUID)

        try:
            index = uuid_servers.index(current_mosque)
            default_name = name_servers[index]
        except ValueError:
            default_name = name_servers[0]

        options = {
            vol.Required(
                CONF_CALC_METHOD,
                default=default_name,
            ): vol.In(name_servers)
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(options),
            description_placeholders={"mawaqit_url": MAWAQIT_URL},
        )
