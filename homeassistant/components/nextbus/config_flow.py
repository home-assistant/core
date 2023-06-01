"""Config flow to configure the Nextbus integration."""
import logging

from py_nextbus import NextBusClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_AGENCY, CONF_ROUTE, CONF_STOP, DOMAIN
from .util import UserConfig

_LOGGER = logging.getLogger(__name__)


def _dict_to_select_selector(options: dict[str, str]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(value=key, label=value)
                for key, value in options.items()
            ],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _get_agency_tags(client: NextBusClient) -> dict[str, str]:
    return {a["tag"]: a["title"] for a in client.get_agency_list()["agency"]}


def _get_route_tags(client: NextBusClient, agency_tag: str) -> dict[str, str]:
    return {a["tag"]: a["title"] for a in client.get_route_list(agency_tag)["route"]}


def _get_stop_tags(
    client: NextBusClient, agency_tag: str, route_tag: str
) -> dict[str, str]:
    return {
        a["tag"]: a["title"]
        for a in client.get_route_config(route_tag, agency_tag)["route"]["stop"]
    }


class NextBusFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Nextbus configuration."""

    VERSION = 1

    _agency_tags: dict[str, str]
    _route_tags: dict[str, str]
    _stop_tags: dict[str, str]

    def __init__(self):
        """Initialize NextBus config flow."""
        self.data: dict[str, str] = {}
        self._client = NextBusClient(output_format="json")
        _LOGGER.info("Init new config flow")

    async def async_step_import(self, config_input: UserConfig) -> FlowResult:
        """Handle import of config."""
        agency = config_input[CONF_AGENCY]
        route = config_input[CONF_ROUTE]
        stop = config_input[CONF_STOP]

        agency_tags = await self.hass.async_add_executor_job(
            _get_agency_tags, self._client
        )
        if agency not in agency_tags:
            return self.async_abort(reason="invalid_agency")

        route_tags = await self.hass.async_add_executor_job(
            _get_route_tags, self._client, agency
        )
        if route not in route_tags:
            return self.async_abort(reason="invalid_route")

        stop_tags = await self.hass.async_add_executor_job(
            _get_stop_tags, self._client, agency, route
        )
        if stop not in stop_tags:
            return self.async_abort(reason="invalid_stop")

        self.data = {
            CONF_AGENCY: agency,
            CONF_ROUTE: route,
            CONF_STOP: stop,
        }

        # Abort if duplicate entries exist
        self._async_abort_entries_match(self.data)

        return self.async_create_entry(
            title=(
                config_input.get(CONF_NAME)
                or f"{config_input[CONF_AGENCY]} {config_input[CONF_ROUTE]}"
            ),
            data=self.data,
        )

    async def async_step_user(
        self,
        user_input: UserConfig | None = None,
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        return await self.async_step_agency(user_input)

    async def async_step_agency(
        self,
        user_input: UserConfig | None = None,
    ) -> FlowResult:
        """Select agency."""
        if user_input is not None:
            self.data[CONF_AGENCY] = user_input[CONF_AGENCY]

            return await self.async_step_route()

        self._agency_tags = await self.hass.async_add_executor_job(
            _get_agency_tags, self._client
        )

        return self.async_show_form(
            step_id="agency",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AGENCY): _dict_to_select_selector(
                        self._agency_tags
                    ),
                }
            ),
        )

    async def async_step_route(
        self,
        user_input: UserConfig | None = None,
    ) -> FlowResult:
        """Select route."""
        if user_input is not None:
            self.data[CONF_ROUTE] = user_input[CONF_ROUTE]

            return await self.async_step_stop()

        self._route_tags = await self.hass.async_add_executor_job(
            _get_route_tags, self._client, self.data[CONF_AGENCY]
        )

        return self.async_show_form(
            step_id="route",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ROUTE): _dict_to_select_selector(
                        self._route_tags
                    ),
                }
            ),
        )

    async def async_step_stop(
        self,
        user_input: UserConfig | None = None,
    ) -> FlowResult:
        """Select stop."""

        if user_input is not None:
            self.data[CONF_STOP] = user_input[CONF_STOP]

            return await self.async_step_name()

        self._stop_tags = await self.hass.async_add_executor_job(
            _get_stop_tags,
            self._client,
            self.data[CONF_AGENCY],
            self.data[CONF_ROUTE],
        )

        return self.async_show_form(
            step_id="stop",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STOP): _dict_to_select_selector(self._stop_tags),
                }
            ),
        )

    async def async_step_name(
        self,
        _: UserConfig | None = None,
    ) -> FlowResult:
        """Set name based on agency, route, and stop."""

        # Abort if duplicate entries exist
        self._async_abort_entries_match(self.data)

        agency_tag = self.data[CONF_AGENCY]
        route_tag = self.data[CONF_ROUTE]
        stop_tag = self.data[CONF_STOP]

        agency_name = self._agency_tags[agency_tag]
        route_name = self._route_tags[route_tag]
        stop_name = self._stop_tags[stop_tag]

        return self.async_create_entry(
            title=f"{agency_name} {route_name} {stop_name}",
            data=self.data,
        )
