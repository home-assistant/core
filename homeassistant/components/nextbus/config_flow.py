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


class NextBusFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Nextbus configuration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize NextBus config flow."""
        self.nextbus_config: dict[str, str] = {}
        self._client = NextBusClient(output_format="json")
        self._agency_tags: dict[str, str] = {}
        self._route_tags: dict[str, str] = {}
        self._stop_tags: dict[str, str] = {}
        _LOGGER.info("Init new config flow")

    async def _update_agency_config_options(self) -> None:
        def job():
            self._agency_tags = {
                a["tag"]: a["title"] for a in self._client.get_agency_list()["agency"]
            }

        await self.hass.async_add_executor_job(job)

    async def _update_route_config_options(self, agency_tag: str) -> None:
        def job():
            self._route_tags = {
                a["tag"]: a["title"]
                for a in self._client.get_route_list(agency_tag)["route"]
            }

        await self.hass.async_add_executor_job(job)

    async def _update_stop_config_options(
        self, agency_tag: str, route_tag: str
    ) -> None:
        def job():
            self._stop_tags = {
                a["tag"]: a["title"]
                for a in self._client.get_route_config(
                    route_tag,
                    agency_tag,
                )[
                    "route"
                ]["stop"]
            }

        await self.hass.async_add_executor_job(job)

    async def async_step_import(
        self, config_input: UserConfig | None = None
    ) -> FlowResult:
        """Handle import of config."""
        if not config_input:
            return self.async_abort(
                reason="Import failed due to no data to migrate",
            )

        await self._update_agency_config_options()
        self.nextbus_config[CONF_AGENCY] = config_input[CONF_AGENCY]

        await self._update_route_config_options(config_input[CONF_AGENCY])
        self.nextbus_config[CONF_ROUTE] = config_input[CONF_ROUTE]

        await self._update_stop_config_options(
            config_input[CONF_AGENCY], config_input[CONF_ROUTE]
        )
        self.nextbus_config[CONF_STOP] = config_input[CONF_STOP]

        self.nextbus_config[CONF_NAME] = (
            config_input.get(CONF_NAME)
            or f"{config_input[CONF_AGENCY]} {config_input[CONF_ROUTE]}"
        )

        errors = self._validate_config()
        if errors:
            _LOGGER.error(errors)
            return await self.async_step_user()

        return self.async_create_entry(
            title=self.nextbus_config[CONF_NAME],
            data=self.nextbus_config,
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
        errors: dict[str, str] = {}

        await self._update_agency_config_options()

        if user_input is not None:
            self.nextbus_config[CONF_AGENCY] = user_input[CONF_AGENCY]
            errors.update(self._validate_config())

            if not errors:
                return await self.async_step_route()

        return self.async_show_form(
            step_id="agency",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AGENCY): _dict_to_select_selector(
                        self._agency_tags
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_route(
        self,
        user_input: UserConfig | None = None,
    ) -> FlowResult:
        """Select route."""
        errors: dict[str, str] = {}

        agency_tag = self.nextbus_config.get(CONF_AGENCY)
        if not agency_tag:
            return await self.async_step_agency()

        await self._update_route_config_options(agency_tag)

        if user_input is not None:
            self.nextbus_config[CONF_ROUTE] = user_input[CONF_ROUTE]
            errors.update(self._validate_config())

            if not errors:
                return await self.async_step_stop()

        return self.async_show_form(
            step_id="route",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ROUTE): _dict_to_select_selector(
                        self._route_tags
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_stop(
        self,
        user_input: UserConfig | None = None,
    ) -> FlowResult:
        """Select stop."""
        errors: dict[str, str] = {}

        agency_tag = self.nextbus_config.get(CONF_AGENCY)
        route_tag = self.nextbus_config.get(CONF_ROUTE)

        if not agency_tag:
            # How did we get here? Go back
            return await self.async_step_agency()

        if not route_tag:
            # How did we get here? Go back
            return await self.async_step_route()

        await self._update_stop_config_options(agency_tag, route_tag)

        if user_input is not None:
            self.nextbus_config[CONF_STOP] = user_input[CONF_STOP]
            errors.update(self._validate_config())

            if not errors:
                return await self.async_step_name()

        return self.async_show_form(
            step_id="stop",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STOP): _dict_to_select_selector(self._stop_tags),
                }
            ),
            errors=errors,
        )

    async def async_step_name(
        self,
        _: UserConfig | None = None,
    ) -> FlowResult:
        """Set name."""
        agency_tag = self.nextbus_config.get(CONF_AGENCY)
        route_tag = self.nextbus_config.get(CONF_ROUTE)
        stop_tag = self.nextbus_config.get(CONF_STOP)

        if not agency_tag:
            # How did we get here? Go back
            return await self.async_step_agency()

        if not route_tag:
            # How did we get here? Go back
            return await self.async_step_route()

        if not stop_tag:
            # How did we get here? Go back
            return await self.async_step_stop()

        agency_name = self._agency_tags[agency_tag]
        route_name = self._route_tags[route_tag]
        stop_name = self._stop_tags[stop_tag]

        return self.async_create_entry(
            title=f"{agency_name} {route_name} {stop_name}",
            data=self.nextbus_config,
        )

    def _validate_config(self) -> dict[str, str]:
        errors: dict[str, str] = {}
        for field, values in (
            (CONF_AGENCY, self._agency_tags),
            (CONF_ROUTE, self._route_tags),
            (CONF_STOP, self._stop_tags),
        ):
            value = self.nextbus_config.get(field)
            if value and value not in values:
                _LOGGER.debug("%s not in %s", value, values)
                errors[field] = "invalid_tag"

        return errors
