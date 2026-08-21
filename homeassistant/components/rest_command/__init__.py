"""Support for exposing regular REST commands as actions."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CONFIG_ENTRY_ID,
    CONF_AUTHENTICATION,
    CONF_HEADERS,
    CONF_METHOD,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_TIMEOUT,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
    SERVICE_RELOAD,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.selector import ConfigEntrySelector
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CONTENT_TYPE,
    CONF_INSECURE_CIPHER,
    CONF_SKIP_URL_ENCODING,
    DEFAULT_METHOD,
    DEFAULT_TIMEOUT,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    SERVICE_CALL_ENDPOINT,
    SUPPORTED_REST_METHODS,
)
from .http import RestCommandRequest

type RestCommandConfigEntry = ConfigEntry[RestCommandRequest]

COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): cv.template,
        vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): vol.All(
            vol.Lower, vol.In(SUPPORTED_REST_METHODS)
        ),
        vol.Optional(CONF_HEADERS): vol.Schema({cv.string: cv.template}),
        vol.Optional(CONF_AUTHENTICATION): vol.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        vol.Inclusive(CONF_USERNAME, "authentication"): cv.string,
        vol.Inclusive(CONF_PASSWORD, "authentication"): cv.string,
        vol.Optional(CONF_PAYLOAD): cv.template,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.Coerce(int),
        vol.Optional(CONF_CONTENT_TYPE): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        vol.Optional(CONF_INSECURE_CIPHER, default=False): cv.boolean,
        vol.Optional(CONF_SKIP_URL_ENCODING, default=False): cv.boolean,
    }
)

RESERVED_ACTIONS = {SERVICE_RELOAD}


def _validate_yaml_action_names(
    commands: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Reject YAML names owned by integration actions."""
    if reserved_names := RESERVED_ACTIONS.intersection(commands):
        reserved_name = min(reserved_names)
        raise vol.Invalid(
            f'The RESTful Command action name "{reserved_name}" is reserved'
        )
    return commands


YAML_COMMANDS_SCHEMA = vol.All(
    _validate_yaml_action_names, cv.schema_with_slug_keys(COMMAND_SCHEMA)
)

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN, default={}): YAML_COMMANDS_SCHEMA}, extra=vol.ALLOW_EXTRA
)

CALL_ENDPOINT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
        vol.Optional(CONF_PAYLOAD): cv.string,
    }
)

CALL_ENDPOINT_SERVICE_DESCRIPTION = {
    "fields": {
        ATTR_CONFIG_ENTRY_ID: {
            "required": True,
            "selector": {"config_entry": {"integration": DOMAIN}},
        },
        CONF_PAYLOAD: {
            "example": '{"message": "The event occurred"}',
            "selector": {"text": {"multiline": True}},
        },
    }
}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the REST command component."""

    async def async_call_endpoint_handler(call: ServiceCall) -> ServiceResponse:
        """Send a request using a UI-managed endpoint."""
        entry: RestCommandConfigEntry = service.async_get_config_entry(
            hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
        )
        return await entry.runtime_data.async_call(
            entry.data[CONF_URL],
            call.data.get(CONF_PAYLOAD, entry.data.get(CONF_PAYLOAD)),
            {},
            call.return_response,
        )

    @callback
    def async_register_call_endpoint() -> None:
        """Register the action for UI-managed endpoints."""
        hass.services.async_register(
            DOMAIN,
            SERVICE_CALL_ENDPOINT,
            async_call_endpoint_handler,
            schema=CALL_ENDPOINT_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
        service.async_set_service_schema(
            hass,
            DOMAIN,
            SERVICE_CALL_ENDPOINT,
            CALL_ENDPOINT_SERVICE_DESCRIPTION,
        )

    async def reload_service_handler(call: ServiceCall) -> None:
        """Remove all rest_commands and load new ones from config."""
        conf = await async_integration_yaml_config(hass, DOMAIN)

        # conf will be None if the configuration can't be parsed
        if conf is None:
            return

        commands = _validate_yaml_action_names(conf[DOMAIN])
        existing = hass.services.async_services_for_domain(DOMAIN)
        for existing_service in existing:
            if existing_service in RESERVED_ACTIONS:
                continue
            hass.services.async_remove(DOMAIN, existing_service)

        async_register_call_endpoint()
        for name, command_config in commands.items():
            async_register_rest_command(name, command_config)

    @callback
    def async_register_rest_command(name: str, command_config: dict[str, Any]) -> None:
        """Create service for rest command."""
        request = RestCommandRequest(hass, command_config)
        template_url = command_config[CONF_URL]
        template_payload = command_config.get(CONF_PAYLOAD)
        template_headers = command_config.get(CONF_HEADERS, {})

        async def async_service_handler(call: ServiceCall) -> ServiceResponse:
            """Execute a RESTful Command action."""
            payload = None
            if template_payload:
                payload = template_payload.async_render(
                    variables=call.data, parse_result=False
                )

            request_url = template_url.async_render(
                variables=call.data, parse_result=False
            )

            headers = {}
            for header_name, template_header in template_headers.items():
                headers[header_name] = template_header.async_render(
                    variables=call.data, parse_result=False
                )

            return await request.async_call(
                request_url, payload, headers, call.return_response
            )

        # register services
        hass.services.async_register(
            DOMAIN,
            name,
            async_service_handler,
            supports_response=SupportsResponse.OPTIONAL,
        )
        if name == SERVICE_CALL_ENDPOINT:
            service.async_set_service_schema(hass, DOMAIN, name, {})

    async_register_call_endpoint()
    for name, command_config in config.get(DOMAIN, {}).items():
        async_register_rest_command(name, command_config)

    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, reload_service_handler, schema=vol.Schema({})
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: RestCommandConfigEntry) -> bool:
    """Set up a UI-managed RESTful Command endpoint."""
    entry.runtime_data = RestCommandRequest(hass, dict(entry.data))
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: RestCommandConfigEntry
) -> None:
    """Reload an updated endpoint."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: RestCommandConfigEntry
) -> bool:
    """Unload a UI-managed RESTful Command endpoint."""
    return True
