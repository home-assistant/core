"""Support for Alexa skill service end point."""

import hmac
from http import HTTPStatus
import logging
import uuid

from aiohttp.web_response import StreamResponse

from homeassistant.components import http
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import template
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

from .const import (
    API_PASSWORD,
    ATTR_MAIN_TEXT,
    ATTR_REDIRECTION_URL,
    ATTR_STREAM_URL,
    ATTR_TITLE_TEXT,
    ATTR_UID,
    ATTR_UPDATE_DATE,
    CONF_AUDIO,
    CONF_DISPLAY_URL,
    CONF_TEXT,
    CONF_TITLE,
    CONF_UID,
    DATE_FORMAT,
)

_LOGGER = logging.getLogger(__name__)

FLASH_BRIEFINGS_API_ENDPOINT = "/api/alexa/flash_briefings/{briefing_id}"


@callback
def async_setup(hass: HomeAssistant, flash_briefing_config: ConfigType) -> None:
    """Activate Alexa component."""
    hass.http.register_view(AlexaFlashBriefingView(hass, flash_briefing_config))


class AlexaFlashBriefingView(http.HomeAssistantView):
    """Handle Alexa Flash Briefing skill requests."""

    url = FLASH_BRIEFINGS_API_ENDPOINT
    requires_auth = False
    name = "api:alexa:flash_briefings"

    def __init__(self, hass: HomeAssistant, flash_briefings: ConfigType) -> None:
        """Initialize Alexa view."""
        super().__init__()
        self.flash_briefings = flash_briefings

    @callback
    def get(self, request: http.HomeAssistantRequest, briefing_id: str) -> StreamResponse | tuple[bytes, HTTPStatus]:
        """Handle Alexa Flash Briefing request."""
        _LOGGER.debug("Received Alexa flash briefing request for: %s", briefing_id)

        if not self._validate_request(request, briefing_id):
            return b"", HTTPStatus.UNAUTHORIZED

        briefing_items = self.flash_briefings.get(briefing_id)
        if not isinstance(briefing_items, list):
            _LOGGER.error("No configured Alexa flash briefing found for: %s", briefing_id)
            return b"", HTTPStatus.NOT_FOUND
        briefing = [self._process_item(item) for item in briefing_items]
        return self.json(briefing)
    

    def _validate_request(self, request, briefing_id):
        """Validate the request for authorization."""
        if request.query.get(API_PASSWORD) is None:
            _LOGGER.error("No password provided for Alexa flash briefing: %s", briefing_id)
            return False
        if not hmac.compare_digest(
            request.query[API_PASSWORD].encode("utf-8"),
            self.flash_briefings[CONF_PASSWORD].encode("utf-8"),
        ):
            _LOGGER.error("Wrong password for Alexa flash briefing: %s", briefing_id)
            return False
        return True
    

        # Process each briefing item.
    def _process_item(self, item: dict) -> dict:
        
        output = {
            ATTR_TITLE_TEXT: self._render_if_template(item, CONF_TITLE),
            ATTR_MAIN_TEXT: self._render_if_template(item, CONF_TEXT),
            ATTR_UID: item.get(CONF_UID, str(uuid.uuid4())),
            ATTR_STREAM_URL: self._render_if_template(item, CONF_AUDIO),
            ATTR_REDIRECTION_URL: self._render_if_template(item, CONF_DISPLAY_URL),
            ATTR_UPDATE_DATE: dt_util.utcnow().strftime(DATE_FORMAT),
        }
        return output


        # Render the value if it's a template, otherwise return the raw value.
    def _render_if_template(self, item: dict, key: str) -> str | None:
        value = item.get(key)
        if isinstance(value, template.Template):
            return value.async_render(parse_result=False)
        return value

