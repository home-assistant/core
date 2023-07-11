"""Alexa HTTP interface."""
import logging

from homeassistant import core
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .auth import Auth
from .config import AbstractConfig
from .const import CONF_ENDPOINT, CONF_ENTITY_CONFIG, CONF_FILTER, CONF_LOCALE
from .smart_home import async_handle_message

_LOGGER = logging.getLogger(__name__)
SMART_HOME_HTTP_ENDPOINT = "/api/alexa/smart_home"


class AlexaConfig(AbstractConfig):
    """Alexa config."""

    def __init__(self, hass, config):
        """Initialize Alexa config."""
        super().__init__(hass)
        self._config = config

        if config.get(CONF_CLIENT_ID) and config.get(CONF_CLIENT_SECRET):
            self._auth = Auth(hass, config[CONF_CLIENT_ID], config[CONF_CLIENT_SECRET])
        else:
            self._auth = None

    @property
    def supports_auth(self):
        """Return if config supports auth."""
        return self._auth is not None

    @property
    def should_report_state(self):
        """Return if we should proactively report states."""
        return self._auth is not None and self.authorized

    @property
    def endpoint(self):
        """Endpoint for report state."""
        return self._config.get(CONF_ENDPOINT)

    @property
    def entity_config(self):
        """Return entity config."""
        return self._config.get(CONF_ENTITY_CONFIG) or {}

    @property
    def locale(self):
        """Return config locale."""
        return self._config.get(CONF_LOCALE)

    @core.callback
    def user_identifier(self):
        """Return an identifier for the user that represents this config."""
        return ""

    @core.callback
    def should_expose(self, entity_id):
        """If an entity should be exposed."""
        if not self._config[CONF_FILTER].empty_filter:
            return self._config[CONF_FILTER](entity_id)

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
    def async_invalidate_access_token(self):
        """Invalidate access token."""
        self._auth.async_invalidate_access_token()

    async def async_get_access_token(self):
        """Get an access token."""
        return await self._auth.async_get_access_token()

    async def async_accept_grant(self, code):
        """Accept a grant."""
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

    def __init__(self, smart_home_config):
        """Initialize."""
        self.smart_home_config = smart_home_config

    async def post(self, request):
        """Handle Alexa Smart Home requests.

        The Smart Home API requires the endpoint to be implemented in AWS
        Lambda, which will need to forward the requests to here and pass back
        the response.
        """
        hass = request.app["hass"]
        user = request["hass_user"]
        message = await request.json()

        _LOGGER.debug("Received Alexa Smart Home request: %s", message)

        response = await async_handle_message(
            hass, self.smart_home_config, message, context=core.Context(user_id=user.id)
        )
        _LOGGER.debug("Sending Alexa Smart Home response: %s", response)
        return b"" if response is None else self.json(response)
