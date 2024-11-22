"""Config flow to configure the Nextbus integration."""

from collections import Counter
import logging

from py_nextbus import NextBusClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_STOP
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_AGENCY, CONF_ROUTE, DOMAIN
from .util import listify

_LOGGER = logging.getLogger(__name__)


def _dict_to_select_selector(options: dict[str, str]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=sorted(
                (
                    SelectOptionDict(value=key, label=value)
                    for key, value in options.items()
                ),
                key=lambda o: o["label"],
            ),
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _get_agency_tags(client: NextBusClient) -> dict[str, str]:
    return {a["id"]: a["name"] for a in client.agencies()}


def _get_route_tags(client: NextBusClient, agency_tag: str) -> dict[str, str]:
    return {a["id"]: a["title"] for a in client.routes(agency_tag)}


def _get_stop_tags(
    client: NextBusClient, agency_tag: str, route_tag: str
) -> dict[str, str]:
    route_config = client.route_details(route_tag, agency_tag)
    stop_ids = {a["id"]: a["name"] for a in route_config["stops"]}
    title_counts = Counter(stop_ids.values())

    stop_directions: dict[str, str] = {}
    for direction in listify(route_config["directions"]):
        if not direction["useForUi"]:
            continue
        for stop in direction["stops"]:
            stop_directions[stop] = direction["name"]

    # Append directions for stops with shared titles
    for stop_id, title in stop_ids.items():
        if title_counts[title] > 1:
            stop_ids[stop_id] = f"{title} ({stop_directions.get(stop_id, stop_id)})"

    return stop_ids


def _unique_id_from_data(data: dict[str, str]) -> str:
    return f"{data[CONF_AGENCY]}_{data[CONF_ROUTE]}_{data[CONF_STOP]}"


class NextBusFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle Nextbus configuration."""

    VERSION = 1

    _agency_tags: dict[str, str]
    _route_tags: dict[str, str]
    _stop_tags: dict[str, str]

    def __init__(self) -> None:
        """Initialize NextBus config flow."""
        self.data: dict[str, str] = {}
        self._client = NextBusClient()

    async def async_step_user(
        self,
        user_input: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        return await self.async_step_agency(user_input)

    async def async_step_agency(
        self,
        user_input: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
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
        user_input: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
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
        user_input: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Select stop."""

        if user_input is not None:
            self.data[CONF_STOP] = user_input[CONF_STOP]

            await self.async_set_unique_id(_unique_id_from_data(self.data))
            self._abort_if_unique_id_configured()

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
