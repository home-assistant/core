"""Config flow for Remote Home-Assistant integration."""
import logging
import enum

from urllib.parse import urlparse

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries, core
from homeassistant.const import (CONF_ABOVE, CONF_ACCESS_TOKEN, CONF_BELOW,
                                 CONF_ENTITY_ID, CONF_HOST, CONF_PORT,
                                 CONF_UNIT_OF_MEASUREMENT, CONF_VERIFY_SSL, CONF_TYPE)
from homeassistant.core import callback
from homeassistant.helpers.instance_id import async_get
from homeassistant.util import slugify

from . import async_yaml_to_config_entry
from .const import (CONF_ENTITY_PREFIX,  # pylint:disable=unused-import
                    CONF_EXCLUDE_DOMAINS, CONF_EXCLUDE_ENTITIES, CONF_FILTER,
                    CONF_INCLUDE_DOMAINS, CONF_INCLUDE_ENTITIES,
                    CONF_LOAD_COMPONENTS, CONF_MAIN, CONF_OPTIONS, CONF_REMOTE, CONF_REMOTE_CONNECTION,
                    CONF_SECURE, CONF_SERVICE_PREFIX, CONF_SERVICES,
                    CONF_SUBSCRIBE_EVENTS, DOMAIN, REMOTE_ID)
from .rest_api import (ApiProblem, CannotConnect, EndpointMissing, InvalidAuth,
                       UnsupportedVersion, async_get_discovery_info)

_LOGGER = logging.getLogger(__name__)

ADD_NEW_EVENT = "add_new_event"

FILTER_OPTIONS = [CONF_ENTITY_ID, CONF_UNIT_OF_MEASUREMENT, CONF_ABOVE, CONF_BELOW]


def _filter_str(index, filter):
    entity_id = filter[CONF_ENTITY_ID]
    unit = filter[CONF_UNIT_OF_MEASUREMENT]
    above = filter[CONF_ABOVE]
    below = filter[CONF_BELOW]
    return f"{index+1}. {entity_id}, unit: {unit}, above: {above}, below: {below}"


async def validate_input(hass: core.HomeAssistant, conf):
    """Validate the user input allows us to connect."""
    try:
        info = await async_get_discovery_info(
            hass,
            conf[CONF_HOST],
            conf[CONF_PORT],
            conf.get(CONF_SECURE, False),
            conf[CONF_ACCESS_TOKEN],
            conf.get(CONF_VERIFY_SSL, False),
        )
    except OSError:
        raise CannotConnect()

    return {"title": info["location_name"], "uuid": info["uuid"]}


class InstanceType(enum.Enum):
    """Possible options for instance type."""

    remote = "Setup as remote node"
    main = "Add a remote"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Remote Home-Assistant."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize a new ConfigFlow."""
        self.prefill = {CONF_PORT: 8123, CONF_SECURE: True}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            if user_input[CONF_TYPE] == CONF_REMOTE:
                await self.async_set_unique_id(REMOTE_ID)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Remote instance", data=user_input)

            elif user_input[CONF_TYPE] == CONF_MAIN:
                return await self.async_step_connection_details()
            
            errors["base"] = "unknown"
            
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TYPE): vol.In([CONF_REMOTE, CONF_MAIN])
                }
            ),
            errors=errors,
        )


    async def async_step_connection_details(self, user_input=None):
        """Handle the connection details step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except ApiProblem:
                errors["base"] = "api_problem"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except UnsupportedVersion:
                errors["base"] = "unsupported_version"
            except EndpointMissing:
                errors["base"] = "missing_endpoint"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["uuid"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        host = self.prefill.get(CONF_HOST) or vol.UNDEFINED
        port = self.prefill.get(CONF_PORT) or vol.UNDEFINED
        secure = self.prefill.get(CONF_SECURE) or vol.UNDEFINED
        return self.async_show_form(
            step_id="connection_details",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=host): str,
                    vol.Required(CONF_PORT, default=port): int,
                    vol.Required(CONF_ACCESS_TOKEN): str,
                    vol.Optional(CONF_SECURE, default=secure): bool,
                    vol.Optional(CONF_VERIFY_SSL, default=True): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_zeroconf(self, info):
        """Handle instance discovered via zeroconf."""
        properties = info.properties
        port = info.port
        uuid = properties["uuid"]

        await self.async_set_unique_id(uuid)
        self._abort_if_unique_id_configured()

        if await async_get(self.hass) == uuid:
            return self.async_abort(reason="already_configured")

        url = properties.get("internal_url")
        if not url:
            url = properties.get("base_url")
        url = urlparse(url)

        self.prefill = {
            CONF_HOST: url.hostname,
            CONF_PORT: port,
            CONF_SECURE: url.scheme == "https",
        }

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context["identifier"] = self.unique_id
        self.context["title_placeholders"] = {"name": properties["location_name"]}
        return await self.async_step_connection_details()

    async def async_step_import(self, user_input):
        """Handle import from YAML."""
        try:
            info = await validate_input(self.hass, user_input)
        except Exception:
            _LOGGER.exception(f"import of {user_input[CONF_HOST]} failed")
            return self.async_abort(reason="import_failed")

        conf, options = async_yaml_to_config_entry(user_input)

        # Options cannot be set here, so store them in a special key and import them
        # before setting up an entry
        conf[CONF_OPTIONS] = options

        await self.async_set_unique_id(info["uuid"])
        self._abort_if_unique_id_configured(updates=conf)

        return self.async_create_entry(title=f"{info['title']} (YAML)", data=conf)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for the Home Assistant remote integration."""

    def __init__(self, config_entry):
        """Initialize remote_homeassistant options flow."""
        self.config_entry = config_entry
        self.filters = None
        self.events = None
        self.options = None

    async def async_step_init(self, user_input=None):
        """Manage basic options."""
        if self.config_entry.unique_id == REMOTE_ID:
            return
        
        if user_input is not None:
            self.options = user_input.copy()
            return await self.async_step_domain_entity_filters()

        domains, _ = self._domains_and_entities()
        domains = set(domains + self.config_entry.options.get(CONF_LOAD_COMPONENTS, []))

        remote = self.hass.data[DOMAIN][self.config_entry.entry_id][
            CONF_REMOTE_CONNECTION
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ENTITY_PREFIX,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_ENTITY_PREFIX
                            )
                        },
                    ): str,
                    vol.Optional(
                        CONF_LOAD_COMPONENTS,
                        default=self._default(CONF_LOAD_COMPONENTS),
                    ): cv.multi_select(sorted(domains)),
                    vol.Required(
                        CONF_SERVICE_PREFIX, default=slugify(self.config_entry.title)
                    ): str,
                    vol.Optional(
                        CONF_SERVICES,
                        default=self._default(CONF_SERVICES),
                    ): cv.multi_select(remote.proxy_services.services),
                }
            ),
        )

    async def async_step_domain_entity_filters(self, user_input=None):
        """Manage domain and entity filters."""
        if user_input is not None:
            self.options.update(user_input)
            return await self.async_step_general_filters()

        domains, entities = self._domains_and_entities()
        return self.async_show_form(
            step_id="domain_entity_filters",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_INCLUDE_DOMAINS,
                        default=self._default(CONF_INCLUDE_DOMAINS),
                    ): cv.multi_select(domains),
                    vol.Optional(
                        CONF_INCLUDE_ENTITIES,
                        default=self._default(CONF_INCLUDE_ENTITIES),
                    ): cv.multi_select(entities),
                    vol.Optional(
                        CONF_EXCLUDE_DOMAINS,
                        default=self._default(CONF_EXCLUDE_DOMAINS),
                    ): cv.multi_select(domains),
                    vol.Optional(
                        CONF_EXCLUDE_ENTITIES,
                        default=self._default(CONF_EXCLUDE_ENTITIES),
                    ): cv.multi_select(entities),
                }
            ),
        )

    async def async_step_general_filters(self, user_input=None):
        """Manage domain and entity filters."""
        if user_input is not None:
            # Continue to next step if entity id is not specified
            if CONF_ENTITY_ID not in user_input:
                # Each filter string is prefixed with a number (index in self.filter+1).
                # Extract all of them and build the final filter list.
                selected_indices = [
                    int(filter.split(".")[0]) - 1
                    for filter in user_input.get(CONF_FILTER, [])
                ]
                self.options[CONF_FILTER] = [self.filters[i] for i in selected_indices]
                return await self.async_step_events()

            selected = user_input.get(CONF_FILTER, [])
            new_filter = {conf: user_input.get(conf) for conf in FILTER_OPTIONS}
            selected.append(_filter_str(len(self.filters), new_filter))
            self.filters.append(new_filter)
        else:
            self.filters = self.config_entry.options.get(CONF_FILTER, [])
            selected = [_filter_str(i, filter) for i, filter in enumerate(self.filters)]

        strings = [_filter_str(i, filter) for i, filter in enumerate(self.filters)]
        return self.async_show_form(
            step_id="general_filters",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_FILTER, default=selected): cv.multi_select(
                        strings
                    ),
                    vol.Optional(CONF_ENTITY_ID): str,
                    vol.Optional(CONF_UNIT_OF_MEASUREMENT): str,
                    vol.Optional(CONF_ABOVE): vol.Coerce(float),
                    vol.Optional(CONF_BELOW): vol.Coerce(float),
                }
            ),
        )

    async def async_step_events(self, user_input=None):
        """Manage event options."""
        if user_input is not None:
            if ADD_NEW_EVENT not in user_input:
                self.options[CONF_SUBSCRIBE_EVENTS] = user_input.get(
                    CONF_SUBSCRIBE_EVENTS, []
                )
                return self.async_create_entry(title="", data=self.options)

            selected = user_input.get(CONF_SUBSCRIBE_EVENTS, [])
            self.events.add(user_input[ADD_NEW_EVENT])
            selected.append(user_input[ADD_NEW_EVENT])
        else:
            self.events = set(
                self.config_entry.options.get(CONF_SUBSCRIBE_EVENTS) or []
            )
            selected = self._default(CONF_SUBSCRIBE_EVENTS)

        return self.async_show_form(
            step_id="events",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SUBSCRIBE_EVENTS, default=selected
                    ): cv.multi_select(self.events),
                    vol.Optional(ADD_NEW_EVENT): str,
                }
            ),
        )

    def _default(self, conf):
        """Return default value for an option."""
        return self.config_entry.options.get(conf) or vol.UNDEFINED

    def _domains_and_entities(self):
        """Return all entities and domains exposed by remote instance."""
        remote = self.hass.data[DOMAIN][self.config_entry.entry_id][
            CONF_REMOTE_CONNECTION
        ]

        # Include entities we have in the config explicitly, otherwise they will be
        # pre-selected and not possible to remove if they are no lobger present on
        # the remote host.
        include_entities = set(self.config_entry.options.get(CONF_INCLUDE_ENTITIES, []))
        exclude_entities = set(self.config_entry.options.get(CONF_EXCLUDE_ENTITIES, []))
        entities = sorted(
            remote._all_entity_names | include_entities | exclude_entities
        )
        domains = sorted(set([entity_id.split(".")[0] for entity_id in entities]))
        return domains, entities
