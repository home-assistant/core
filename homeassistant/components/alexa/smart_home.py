"""Support for alexa Smart Home Skill API."""
import logging
from typing import Any

from aiohttp import web
from yarl import URL

from homeassistant import core
from homeassistant.auth.models import User
from homeassistant.components.http import HomeAssistantRequest
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .auth import Auth
from .config import AbstractConfig
from .const import (
    API_DIRECTIVE,
    API_HEADER,
    CONF_ENDPOINT,
    CONF_ENTITY_CONFIG,
    CONF_FILTER,
    CONF_LOCALE,
    EVENT_ALEXA_SMART_HOME,
)
from .errors import AlexaBridgeUnreachableError, AlexaError
from .handlers import HANDLERS
from .state_report import AlexaDirective

_LOGGER = logging.getLogger(__name__)
SMART_HOME_HTTP_ENDPOINT = "/api/alexa/smart_home"


class AlexaConfig(AbstractConfig):
    """Alexa config."""

    _auth: Auth | None

    def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
        """Initialize Alexa config."""
        super().__init__(hass)
        self._config = config

        if config.get(CONF_CLIENT_ID) and config.get(CONF_CLIENT_SECRET):
            self._auth = Auth(hass, config[CONF_CLIENT_ID], config[CONF_CLIENT_SECRET])
        else:
            self._auth = None

    @property
    def supports_auth(self) -> bool:
        """Return if config supports auth."""
        return self._auth is not None

    @property
    def should_report_state(self) -> bool:
        """Return if we should proactively report states."""
        return self._auth is not None and self.authorized

    @property
    def endpoint(self) -> str | URL | None:
        """Endpoint for report state."""
        return self._config.get(CONF_ENDPOINT)

    @property
    def entity_config(self) -> dict[str, Any]:
        """Return entity config."""
        return self._config.get(CONF_ENTITY_CONFIG) or {}

    @property
    def locale(self) -> str | None:
        """Return config locale."""
        return self._config.get(CONF_LOCALE)

    @core.callback
    def user_identifier(self) -> str:
        """Return an identifier for the user that represents this config."""
        return ""

    @core.callback
    def should_expose(self, entity_id: str) -> bool:
        """If an entity should be exposed."""
        if not self._config[CONF_FILTER].empty_filter:
            return bool(self._config[CONF_FILTER](entity_id))

        entity_registry = er.async_get(self.hass)
        if registry_entry := entity_registry.async_get(entity_id):
            auxiliary_entity = (
                registry_entry.entity_category is not None
                or registry_entry.hidden_by is not None
            )
        else:
            auxiliary_entity = False
        return not auxiliary_entity

    @core.callback
    def async_invalidate_access_token(self) -> None:
        """Invalidate access token."""
        assert self._auth is not None
        self._auth.async_invalidate_access_token()

    async def async_get_access_token(self) -> str | None:
        """Get an access token."""
        assert self._auth is not None
        return await self._auth.async_get_access_token()

    async def async_accept_grant(self, code: str) -> str | None:
        """Accept a grant."""
        assert self._auth is not None
        return await self._auth.async_do_auth(code)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> None:
    """Activate Smart Home functionality of Alexa component.

    This is optional, triggered by having a `smart_home:` sub-section in the
    alexa configuration.

    Even if that's disabled, the functionality in this module may still be used
    by the cloud component which will call async_handle_message directly.
    """
    smart_home_config = AlexaConfig(hass, config)
    await smart_home_config.async_initialize()
    hass.http.register_view(SmartHomeView(smart_home_config))

    if smart_home_config.should_report_state:
        await smart_home_config.async_enable_proactive_mode()


class SmartHomeView(HomeAssistantView):
    """Expose Smart Home v3 payload interface via HTTP POST."""

    url = SMART_HOME_HTTP_ENDPOINT
    name = "api:alexa:smart_home"

    def __init__(self, smart_home_config: AlexaConfig) -> None:
        """Initialize."""
        self.smart_home_config = smart_home_config

    async def post(self, request: HomeAssistantRequest) -> web.Response | bytes:
        """Handle Alexa Smart Home requests.

        The Smart Home API requires the endpoint to be implemented in AWS
        Lambda, which will need to forward the requests to here and pass back
        the response.
        """
        hass: HomeAssistant = request.app["hass"]
        user: User = request["hass_user"]
        message: dict[str, Any] = await request.json()

        _LOGGER.debug("Received Alexa Smart Home request: %s", message)

        response = await async_handle_message(
            hass, self.smart_home_config, message, context=core.Context(user_id=user.id)
        )
        _LOGGER.debug("Sending Alexa Smart Home response: %s", response)
        return b"" if response is None else self.json(response)


async def async_handle_message(
    hass: HomeAssistant,
    config: AbstractConfig,
    request: dict[str, Any],
    context: Context | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    """Handle incoming API messages.

    If enabled is False, the response to all messages will be a
    BRIDGE_UNREACHABLE error. This can be used if the API has been disabled in
    configuration.
    """
    assert request[API_DIRECTIVE][API_HEADER]["payloadVersion"] == "3"

    if context is None:
        context = Context()

    directive = AlexaDirective(request)

    try:
        if not enabled:
            raise AlexaBridgeUnreachableError(
                "Alexa API not enabled in Home Assistant configuration"
            )

        await config.set_authorized(True)

        if directive.has_endpoint:
            directive.load_entity(hass, config)

        funct_ref = HANDLERS.get((directive.namespace, directive.name))
        if funct_ref:
            response = await funct_ref(hass, config, directive, context)
            if directive.has_endpoint:
                response.merge_context_properties(directive.endpoint)
        else:
            _LOGGER.warning(
                "Unsupported API request %s/%s", directive.namespace, directive.name
            )
            response = directive.error()
    except AlexaError as err:
        response = directive.error(
            error_type=str(err.error_type),
            error_message=err.error_message,
            payload=err.payload,
        )
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception(
            "Uncaught exception processing Alexa %s/%s request (%s)",
            directive.namespace,
            directive.name,
            directive.entity_id or "-",
        )
        response = directive.error(error_message="Unknown error")

    request_info: dict[str, Any] = {
        "namespace": directive.namespace,
        "name": directive.name,
    }

    if directive.has_endpoint:
        assert directive.entity_id is not None
        request_info["entity_id"] = directive.entity_id

    hass.bus.async_fire(
        EVENT_ALEXA_SMART_HOME,
        {
            "request": request_info,
            "response": {"namespace": response.namespace, "name": response.name},
        },
        context=context,
    )

    return response.serialize()
