"""Config flow for the Mawaqit integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from aiohttp.client_exceptions import ClientConnectorError
from mawaqit.exceptions import (
    BadCredentialsException,
    MawaqitException,
    NoMosqueAround,
    NoMosqueFound,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME, CONF_UUID
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import mawaqit_wrapper, utils
from .const import (
    CANNOT_CONNECT_TO_SERVER,
    CONF_SEARCH,
    CONF_TYPE_SEARCH,
    CONF_TYPE_SEARCH_COORDINATES,
    CONF_TYPE_SEARCH_KEYWORD,
    CONF_TYPE_SEARCH_TRANSLATION_KEY,
    DOMAIN,
    KEYWORD_SEARCH_NEXT_PAGE,
    KEYWORD_SEARCH_PAGE_SIZE,
    KEYWORD_SEARCH_PREV_PAGE,
    MAWAQIT_URL,
    NO_MOSQUE_FOUND_KEYWORD,
    WRONG_CREDENTIAL,
)
from .types import MawaqitMosqueData

_LOGGER = logging.getLogger(__name__)


class MawaqitPrayerFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for MAWAQIT."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self.previous_keyword_search: str = ""
        self.mosques: dict[str, MawaqitMosqueData] = {}
        self.token: str | None = None
        # keyword search pagination
        self.keyword_page: int = 1
        self.keyword_has_next: bool = False
        self.current_keyword: str = ""

    #############################################
    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle reauthentication."""

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm reauthentication."""

        errors: dict[str, str] = {}

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
                valid = await mawaqit_wrapper.validate_credentials(
                    username,
                    password,
                    session=async_get_clientsession(self.hass),
                )
            except (
                ClientConnectorError,
                ConnectionError,
                TimeoutError,
                MawaqitException,
            ):
                errors["base"] = CANNOT_CONNECT_TO_SERVER
            else:
                if not valid:
                    errors["base"] = WRONG_CREDENTIAL
                else:
                    try:
                        token = await mawaqit_wrapper.get_mawaqit_api_token(
                            username,
                            password,
                            session=async_get_clientsession(self.hass),
                        )
                    except (
                        ClientConnectorError,
                        ConnectionError,
                        TimeoutError,
                        MawaqitException,
                    ):
                        errors["base"] = CANNOT_CONNECT_TO_SERVER
                    else:
                        return self.async_update_reload_and_abort(
                            self._get_reauth_entry(),
                            data_updates={
                                CONF_API_KEY: token,
                            },
                        )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
        )

    #############################################

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""

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
                valid = await mawaqit_wrapper.validate_credentials(
                    username, password, session=async_get_clientsession(self.hass)
                )
            except (
                ClientConnectorError,
                ConnectionError,
                TimeoutError,
                MawaqitException,
            ):
                errors["base"] = CANNOT_CONNECT_TO_SERVER
            else:
                if valid:
                    try:
                        mawaqit_token = await mawaqit_wrapper.get_mawaqit_api_token(
                            username,
                            password,
                            session=async_get_clientsession(self.hass),
                        )
                    except (
                        ClientConnectorError,
                        ConnectionError,
                        TimeoutError,
                        MawaqitException,
                    ):
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
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle mosques step."""

        errors: dict[str, str] = {}

        lat = self.hass.config.latitude
        longi = self.hass.config.longitude

        if user_input is not None:
            mosque_uuid = user_input[CONF_UUID]
            title, data_entry = utils.save_mosque(
                self.mosques[mosque_uuid].display_name,
                mosque_uuid,
                self.token,
                lat,
                longi,
            )
            if self.source == config_entries.SOURCE_RECONFIGURE:
                # reconfigure flow: update existing entry with new data and reload
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(), title=title, data=data_entry
                )
            return self.async_create_entry(title=title, data=data_entry)

        if not self.mosques:
            try:
                neighborhood_mosques = await mawaqit_wrapper.all_mosques_neighborhood(
                    lat,
                    longi,
                    token=self.token,
                    session=async_get_clientsession(self.hass),
                )
                if neighborhood_mosques:
                    self.mosques = {
                        mosque.uuid: mosque for mosque in neighborhood_mosques
                    }
            except NoMosqueAround:
                return self.async_abort(reason="no_mosque")
            except (
                BadCredentialsException,
                ClientConnectorError,
                ConnectionError,
                TimeoutError,
            ):
                return self.async_abort(reason="cannot_connect")

        if len(self.mosques) == 0:
            return self.async_abort(reason="no_mosque")

        return self.async_show_form(
            step_id="mosques_coordinates",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UUID): vol.In(
                        {
                            mosque.uuid: mosque.display_name
                            for mosque in self.mosques.values()
                        }
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_search_method(
        self, user_input: dict[str, Any] | None = None
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
            return await self.async_step_mosques_coordinates()

        if search_method == CONF_TYPE_SEARCH_KEYWORD:
            return await self.async_step_keyword_search()

        return self.async_show_form(
            step_id="search_method",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_keyword_search(
        self, user_input: dict[str, Any] | None = None
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
                    self.mosques[selected_uuid].display_name,
                    selected_uuid,
                    mawaqit_token=self.token,
                )

                if self.source == config_entries.SOURCE_RECONFIGURE:
                    # reconfigure flow: update existing entry with new data and reload
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(), title=title, data=data_entry
                    )

                return self.async_create_entry(title=title, data=data_entry)

            # New keyword: reset to page 1
            if keyword != self.previous_keyword_search:
                self.keyword_page = 1

            self.previous_keyword_search = keyword

            # Fetch the page
            try:
                mosques_result = await mawaqit_wrapper.all_mosques_by_keyword(
                    search_keyword=keyword,
                    page=self.keyword_page,
                    token=self.token,
                    session=async_get_clientsession(self.hass),
                )
                self.mosques = {mosque.uuid: mosque for mosque in mosques_result}
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
                MawaqitException,
            ):
                errors["base"] = CANNOT_CONNECT_TO_SERVER
                return self.async_show_form(
                    step_id="keyword_search",
                    data_schema=self.add_suggested_values_to_schema(
                        vol.Schema(option), {CONF_SEARCH: keyword}
                    ),
                    errors=errors,
                )

            if len(self.mosques) == 0:
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

            nav_options.update(
                {mosque.uuid: mosque.display_name for mosque in self.mosques.values()}
            )

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
                            vol.Required(
                                CONF_UUID, default=list(self.mosques.keys())[0]
                            ): vol.In(nav_options),
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

    async def async_step_reconfigure(
        self, user_input: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration."""
        self.token = self._get_reconfigure_entry().data[CONF_API_KEY]
        return await self.async_step_search_method()
