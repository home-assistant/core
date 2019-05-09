"""Support for Google Actions Smart Home Control."""
import logging

from aiohttp.web import Request, Response

# Typing imports
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback
from homeassistant.const import CLOUD_NEVER_EXPOSED_ENTITIES

from .const import (
    GOOGLE_ASSISTANT_API_ENDPOINT,
    CONF_EXPOSE_BY_DEFAULT,
    CONF_EXPOSED_DOMAINS,
    CONF_ENTITY_CONFIG,
    CONF_EXPOSE,
    CONF_SECURE_DEVICES_PIN,
)
from .smart_home import async_handle_message
from .helpers import Config

_LOGGER = logging.getLogger(__name__)


@callback
def async_register_http(hass, cfg):
    """Register HTTP views for Google Assistant."""
    expose_by_default = cfg.get(CONF_EXPOSE_BY_DEFAULT)
    exposed_domains = cfg.get(CONF_EXPOSED_DOMAINS)
    entity_config = cfg.get(CONF_ENTITY_CONFIG) or {}
    secure_devices_pin = cfg.get(CONF_SECURE_DEVICES_PIN)

    def is_exposed(entity) -> bool:
        """Determine if an entity should be exposed to Google Assistant."""
        if entity.attributes.get('view') is not None:
            # Ignore entities that are views
            return False

        if entity.entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
            return False

        explicit_expose = \
            entity_config.get(entity.entity_id, {}).get(CONF_EXPOSE)

        domain_exposed_by_default = \
            expose_by_default and entity.domain in exposed_domains

        # Expose an entity if the entity's domain is exposed by default and
        # the configuration doesn't explicitly exclude it from being
        # exposed, or if the entity is explicitly exposed
        is_default_exposed = \
            domain_exposed_by_default and explicit_expose is not False

        return is_default_exposed or explicit_expose

    config = Config(
        should_expose=is_exposed,
        entity_config=entity_config,
        secure_devices_pin=secure_devices_pin
    )

    hass.http.register_view(GoogleAssistantView(config))


class GoogleAssistantView(HomeAssistantView):
    """Handle Google Assistant requests."""

    url = GOOGLE_ASSISTANT_API_ENDPOINT
    name = 'api:google_assistant'
    requires_auth = True

    def __init__(self, config):
        """Initialize the Google Assistant request handler."""
        self.config = config

    async def post(self, request: Request) -> Response:
        """Handle Google Assistant requests."""
        message = await request.json()  # type: dict
        result = await async_handle_message(
            request.app['hass'],
            self.config,
            request['hass_user'].id,
            message)
        return self.json(result)
