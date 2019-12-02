"""Config flow for Azure Event Hub integration."""
import logging
from typing import Any, Dict

from azure.eventhub import (
    AuthenticationError,
    ConnectError,
    EventHubSharedKeyCredential,
)
from azure.eventhub.aio import EventHubProducerClient
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import generate_filter

from .const import (
    CONF_EVENT_HUB_CON_STRING,
    CONF_EVENT_HUB_INSTANCE_NAME,
    CONF_EVENT_HUB_NAMESPACE,
    CONF_EVENT_HUB_SAS_KEY,
    CONF_EVENT_HUB_SAS_POLICY,
    CONF_EXCLUDE_DOMAINS,
    CONF_EXCLUDE_ENTITIES,
    CONF_FILTER,
    CONF_INCLUDE_DOMAINS,
    CONF_INCLUDE_ENTITIES,
    DOMAIN,
    FILTER_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_EVENT_HUB_CON_STRING, default=""): str,
        vol.Optional(CONF_EVENT_HUB_NAMESPACE, default=""): str,
        vol.Optional(CONF_EVENT_HUB_INSTANCE_NAME, default=""): str,
        vol.Optional(CONF_EVENT_HUB_SAS_POLICY, default=""): str,
        vol.Optional(CONF_EVENT_HUB_SAS_KEY, default=""): str,
        vol.Optional(CONF_FILTER, default=False): bool,
    },
    extra=vol.ALLOW_EXTRA,
)

FILTER_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_INCLUDE_DOMAINS, default=""): str,
        vol.Optional(CONF_INCLUDE_ENTITIES, default=""): str,
        vol.Optional(CONF_EXCLUDE_DOMAINS, default=""): str,
        vol.Optional(CONF_EXCLUDE_ENTITIES, default=""): str,
    },
    extra=vol.ALLOW_EXTRA,
)

CONFIG_VALIDATION_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_EVENT_HUB_CON_STRING, ""): cv.string,
        vol.Optional(CONF_EVENT_HUB_NAMESPACE, ""): cv.string,
        vol.Optional(CONF_EVENT_HUB_INSTANCE_NAME, ""): cv.string,
        vol.Optional(CONF_EVENT_HUB_SAS_POLICY, ""): cv.string,
        vol.Optional(CONF_EVENT_HUB_SAS_KEY, ""): cv.string,
        vol.Optional(CONF_FILTER, default={}): FILTER_SCHEMA,
    },
    cv.has_at_least_one_key(CONF_EVENT_HUB_CON_STRING, CONF_EVENT_HUB_NAMESPACE),
    extra=vol.ALLOW_EXTRA,
)


@callback
def configured_instances(hass):
    """Return a set of configured AEH instances."""
    return set(entry.title for entry in hass.config_entries.async_entries(DOMAIN))


def valid_domain(hass: HomeAssistant, value: str):
    """Validate a domain in the filter, existing in current HA."""
    domains = hass.data.get("integrations", {}).keys()
    if domains:
        if value in domains:
            return value
        else:
            raise InvalidDomain
    else:
        _LOGGER.info("Domains not available, assuming correctness of Domain")
        return value


def valid_entity(hass: HomeAssistant, value: str):
    """Validate an entity name in the filter, format only."""
    domains = hass.data.get("integrations", {}).keys()
    try:
        value = cv.entity_id(value)
    except Exception:  # pylint: disable=broad-except
        raise InvalidEntity
    if domains:
        # only checks if the domain exists, entity names might not be ready yet.
        if cv.split_entity_id(value)[0] in domains:
            return value
        else:
            raise InvalidEntity
    else:
        _LOGGER.info("Domains not available, assuming correctness of Entity")
        return value


def reformat_config(data: Dict, hass: HomeAssistant):
    """Reformat a config data dict.

    Tt replaces the bool with empty lists and splits the string of filter values into lists.
    """
    config = data.copy()
    if CONF_FILTER in config:
        filter_dict = config[CONF_FILTER]
        if isinstance(filter_dict, bool):
            config[CONF_FILTER] = {}
        else:
            validated_filter = {}
            for k, filter in config[CONF_FILTER].items():
                if isinstance(filter, list):
                    validated_filter[k] = filter
                else:
                    if k in [CONF_EXCLUDE_DOMAINS, CONF_INCLUDE_DOMAINS]:
                        validated_filter[k] = (
                            [valid_domain(hass, f.strip()) for f in filter.split(",")]
                            if filter
                            else []
                        )
                    else:
                        validated_filter[k] = (
                            [valid_entity(hass, f.strip()) for f in filter.split(",")]
                            if filter
                            else []
                        )
            try:
                generate_filter(**validated_filter)
            except Exception:  # pylint: disable=broad-except
                raise InvalidFilter
            config[CONF_FILTER] = validated_filter
    else:
        config[CONF_FILTER] = {}
    return config


async def test_connection(config: Dict):
    """Test the connection to Azure."""
    additional_args = {"retry_total": 0, "auth_timeout": 10, "logging_enable": False}
    if config.get(CONF_EVENT_HUB_CON_STRING, None):
        _LOGGER.debug("Using connection string.")
        client_args = {"conn_str": config[CONF_EVENT_HUB_CON_STRING]}
        try:
            client = EventHubProducerClient.from_connection_string(
                **client_args, **additional_args
            )
        except ValueError as e:  # occurs when the format of a connection string is wrong
            _LOGGER.debug("ValueError: %s", e)
            raise InvalidConnectionString
    elif (
        config.get(CONF_EVENT_HUB_NAMESPACE, None)
        and config.get(CONF_EVENT_HUB_INSTANCE_NAME, None)
        and config.get(CONF_EVENT_HUB_SAS_POLICY, None)
        and config.get(CONF_EVENT_HUB_SAS_KEY, None)
    ):
        _LOGGER.debug("Using connection details.")
        client_args = {
            "host": f"{config[CONF_EVENT_HUB_NAMESPACE]}.servicebus.windows.net",
            "credential": EventHubSharedKeyCredential(
                policy=config[CONF_EVENT_HUB_SAS_POLICY],
                key=config[CONF_EVENT_HUB_SAS_KEY],
            ),
            "event_hub_path": config[CONF_EVENT_HUB_INSTANCE_NAME],
        }
        client = EventHubProducerClient(**client_args, **additional_args)
    else:
        _LOGGER.debug("Incorrect details provided")
        raise InvalidConfig
    try:
        await client.get_partition_ids()
    except (ConnectError, AuthenticationError) as e:
        _LOGGER.debug("Error:, %s", e)
        msg = str(e)
        if "Please confirm target hostname exists" in msg:
            raise InvalidNamespace
        elif "Failed to open mgmt link" in msg:
            raise InvalidInstance
        elif "Token authentication failed" in msg:
            raise InvalidSAS
        else:
            raise CannotConnect
    name = client.eh_name
    await client.close()
    return name


async def validate_input(data: Dict, hass: HomeAssistant):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    config = reformat_config(data, hass)
    try:
        CONFIG_VALIDATION_SCHEMA(config)
    except Exception as e:  # pylint: disable=broad-except
        _LOGGER.debug("Config validation failed: %s", e)
        raise e
    return config, await test_connection(config)


class AzureEventHubConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Azure Event Hub."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    def __init__(self, **kwargs: Any):
        """Initialize."""
        self._errors = {}
        self._init_in_progress = []
        self._from_yaml = False

    async def async_step_import(self, import_config):
        """Import a AEH as a config entry.

        This flow is triggered by `async_setup` for configured devices.
        This flow is also triggered by `async_step_discovery`.

        This will execute for any AEH device that contains a complete
        configuration.
        """
        _LOGGER.debug("Received config from async_setup: %s", import_config)
        self._from_yaml = True
        return await self.async_step_user(user_input=import_config)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        configured = configured_instances(self.hass)
        if len(configured) > 0:
            return self.async_abort(reason="already_configured")
        _LOGGER.info("Running step: user")
        if user_input is not None:
            try:
                _LOGGER.info("Info gathered: %s", user_input)
                config, name = await validate_input(user_input, self.hass)
                if self._from_yaml or not user_input.get(CONF_FILTER):
                    return self.async_create_entry(title=name, data=config)
                else:
                    self._init_in_progress = user_input
                    return await self.async_step_filter()
            except (
                InvalidSAS,
                InvalidConfig,
                InvalidNamespace,
                InvalidInstance,
                InvalidConnectionString,
                InvalidAuth,
                InvalidFilter,
                InvalidDomain,
                InvalidEntity,
                CannotConnect,
            ) as e:
                self._errors["base"] = e.msg
            except Exception as e:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", e)
                self._errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_ENTRY_SCHEMA, errors=self._errors
        )

    async def async_step_filter(self, filter_input=None):
        """Handle the filter step."""
        _LOGGER.info("Running step: filter")
        if filter_input is not None:
            try:
                self._init_in_progress[CONF_FILTER] = filter_input
                config, name = await validate_input(self._init_in_progress, self.hass)
                return self.async_create_entry(title=name, data=config)
            except (
                InvalidSAS,
                InvalidConfig,
                InvalidNamespace,
                InvalidInstance,
                InvalidConnectionString,
                InvalidAuth,
                InvalidFilter,
                InvalidDomain,
                InvalidEntity,
                CannotConnect,
            ) as e:
                self._errors["base"] = e.msg
            except Exception as e:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", e)
                self._errors["base"] = "unknown"
        return self.async_show_form(
            step_id="filter", data_schema=FILTER_ENTRY_SCHEMA, errors=self._errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""

    msg = "cannot_connect"


class InvalidSAS(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

    msg = "invalid_sas"


class InvalidNamespace(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

    msg = "invalid_namespace"


class InvalidInstance(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

    msg = "invalid_instance"


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""

    msg = "invalid_auth"


class InvalidConfig(exceptions.HomeAssistantError):
    """Error to indicate there is invalid config."""

    msg = "invalid_config"


class InvalidConnectionString(exceptions.HomeAssistantError):
    """Error to indicate there is invalid connection string."""

    msg = "invalid_connection_string"


class InvalidFilter(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid filter."""

    msg = "invalid_filter"


class InvalidDomain(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid domain in the filter."""

    msg = "invalid_domain"


class InvalidEntity(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid entity in the filter."""

    msg = "invalid_entity"
