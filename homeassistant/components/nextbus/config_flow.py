"""Config flow to configure the Nextbus integration."""
from collections import Counter
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
    return {a["tag"]: a["title"] for a in client.get_agency_list()["agency"]}


def _get_route_tags(client: NextBusClient, agency_tag: str) -> dict[str, str]:
    return {a["tag"]: a["title"] for a in client.get_route_list(agency_tag)["route"]}


def _get_stop_tags(
    client: NextBusClient, agency_tag: str, route_tag: str
) -> dict[str, str]:
    route_config = client.get_route_config(route_tag, agency_tag)
    tags = {a["tag"]: a["title"] for a in route_config["route"]["stop"]}
    title_counts = Counter(tags.values())

    stop_directions: dict[str, str] = {}
    for direction in listify(route_config["route"]["direction"]):
        for stop in direction["stop"]:
            stop_directions[stop["tag"]] = direction["name"]

    # Append directions for stops with shared titles
    for tag, title in tags.items():
        if title_counts[title] > 1:
            tags[tag] = f"{title} ({stop_directions.get(tag, tag)})"

    return tags


def _validate_import(
    client: NextBusClient, agency_tag: str, route_tag: str, stop_tag: str
) -> str | tuple[str, str, str]:
    agency_tags = _get_agency_tags(client)
    agency = agency_tags.get(agency_tag)
    if not agency:
        return "invalid_agency"

    route_tags = _get_route_tags(client, agency_tag)
    route = route_tags.get(route_tag)
    if not route:
        return "invalid_route"

    stop_tags = _get_stop_tags(client, agency_tag, route_tag)
    stop = stop_tags.get(stop_tag)
    if not stop:
        return "invalid_stop"

    return agency, route, stop


def _unique_id_from_data(data: dict[str, str]) -> str:
    return f"{data[CONF_AGENCY]}_{data[CONF_ROUTE]}_{data[CONF_STOP]}"


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

    async def async_step_import(self, config_input: dict[str, str]) -> FlowResult:
        """Handle import of config."""
        agency_tag = config_input[CONF_AGENCY]
        route_tag = config_input[CONF_ROUTE]
        stop_tag = config_input[CONF_STOP]

        validation_result = await self.hass.async_add_executor_job(
            _validate_import,
            self._client,
            agency_tag,
            route_tag,
            stop_tag,
        )
        if isinstance(validation_result, str):
            return self.async_abort(reason=validation_result)

        data = {
            CONF_AGENCY: agency_tag,
            CONF_ROUTE: route_tag,
            CONF_STOP: stop_tag,
            CONF_NAME: config_input.get(
                CONF_NAME,
                f"{config_input[CONF_AGENCY]} {config_input[CONF_ROUTE]}",
            ),
        }

        await self.async_set_unique_id(_unique_id_from_data(data))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=" ".join(validation_result),
            data=data,
        )

    async def async_step_user(
        self,
        user_input: dict[str, str] | None = None,
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        return await self.async_step_agency(user_input)

    async def async_step_agency(
        self,
        user_input: dict[str, str] | None = None,
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
        user_input: dict[str, str] | None = None,
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
        user_input: dict[str, str] | None = None,
    ) -> FlowResult:
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
