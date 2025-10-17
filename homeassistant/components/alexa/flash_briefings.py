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
from homeassistant.util import dt as dt_util

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
    def get(
        self, request: http.HomeAssistantRequest, briefing_id: str
    ) -> StreamResponse | tuple[bytes, HTTPStatus]:
        """Handle Alexa Flash Briefing request."""
        _LOGGER.debug("Received Alexa flash briefing request for: %s", briefing_id)

        # Validate request
        auth_error = self._validate_authentication(request, briefing_id)
        if auth_error:
            return auth_error

        # Check if briefing exists
        briefing_config = self.flash_briefings.get(briefing_id)
        if not isinstance(briefing_config, list):
            err = "No configured Alexa flash briefing was found for: %s"
            _LOGGER.error(err, briefing_id)
            return b"", HTTPStatus.NOT_FOUND

        # Build briefing response
        briefing = self._build_briefing_response(briefing_config)
        return self.json(briefing)

    def _validate_authentication(
        self, request: http.HomeAssistantRequest, briefing_id: str
    ) -> tuple[bytes, HTTPStatus] | None:
        """Validate request authentication."""
        if request.query.get(API_PASSWORD) is None:
            err = "No password provided for Alexa flash briefing: %s"
            _LOGGER.error(err, briefing_id)
            return b"", HTTPStatus.UNAUTHORIZED

        if not hmac.compare_digest(
            request.query[API_PASSWORD].encode("utf-8"),
            self.flash_briefings[CONF_PASSWORD].encode("utf-8"),
        ):
            err = "Wrong password for Alexa flash briefing: %s"
            _LOGGER.error(err, briefing_id)
            return b"", HTTPStatus.UNAUTHORIZED

        return None

    def _build_briefing_response(self, briefing_config: list) -> list[dict[str, str]]:
        """Build the briefing response from configuration."""
        briefing = []
        for item in briefing_config:
            output = self._process_briefing_item(item)
            briefing.append(output)
        return briefing

    def _process_briefing_item(self, item: dict) -> dict[str, str]:
        """Process a single briefing item."""
        output = {}

        # Process title
        if item.get(CONF_TITLE) is not None:
            output[ATTR_TITLE_TEXT] = self._render_template_or_value(item[CONF_TITLE])

        # Process text
        if item.get(CONF_TEXT) is not None:
            output[ATTR_MAIN_TEXT] = self._render_template_or_value(item[CONF_TEXT])

        # Process UID
        uid = item.get(CONF_UID)
        if uid is None:
            uid = str(uuid.uuid4())
        output[ATTR_UID] = uid

        # Process audio
        if item.get(CONF_AUDIO) is not None:
            output[ATTR_STREAM_URL] = self._render_template_or_value(item[CONF_AUDIO])

        # Process display URL
        if item.get(CONF_DISPLAY_URL) is not None:
            output[ATTR_REDIRECTION_URL] = self._render_template_or_value(
                item[CONF_DISPLAY_URL]
            )

        # Add update date
        output[ATTR_UPDATE_DATE] = dt_util.utcnow().strftime(DATE_FORMAT)

        return output

    def _render_template_or_value(self, value: str | template.Template) -> str:
        """Render template or return value as string."""
        if isinstance(value, template.Template):
            return str(value.async_render(parse_result=False))
        return value
