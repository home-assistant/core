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

        if not self._has_valid_password(request, briefing_id):
            return b"", HTTPStatus.UNAUTHORIZED

        if not isinstance(self.flash_briefings.get(briefing_id), list):
            err = "No configured Alexa flash briefing was found for: %s"
            _LOGGER.error(err, briefing_id)
            return b"", HTTPStatus.NOT_FOUND

        briefing = [
            self._build_briefing_output(item)
            for item in self.flash_briefings.get(briefing_id, [])
        ]

        return self.json(briefing)

    def _has_valid_password(self, request: http.HomeAssistantRequest, briefing_id: str) -> bool:
        """Check if the request has a valid password."""
        if request.query.get(API_PASSWORD) is None:
            err = "No password provided for Alexa flash briefing: %s"
            _LOGGER.error(err, briefing_id)
            return False

        if not hmac.compare_digest(
            request.query[API_PASSWORD].encode("utf-8"),
            self.flash_briefings[CONF_PASSWORD].encode("utf-8"),
        ):
            err = "Wrong password for Alexa flash briefing: %s"
            _LOGGER.error(err, briefing_id)
            return False

        return True

    def _render_value(self, value):
        """Render a template or return the value."""
        if isinstance(value, template.Template):
            return value.async_render(parse_result=False)
        return value

    def _build_briefing_output(self, item: dict) -> dict:
        """Build the output dictionary for a single briefing item."""
        output = {}

        title = item.get(CONF_TITLE)
        if title is not None:
            output[ATTR_TITLE_TEXT] = self._render_value(title)

        text = item.get(CONF_TEXT)
        if text is not None:
            output[ATTR_MAIN_TEXT] = self._render_value(text)

        uid = item.get(CONF_UID) or str(uuid.uuid4())
        output[ATTR_UID] = uid

        audio = item.get(CONF_AUDIO)
        if audio is not None:
            output[ATTR_STREAM_URL] = self._render_value(audio)

        display_url = item.get(CONF_DISPLAY_URL)
        if display_url is not None:
            output[ATTR_REDIRECTION_URL] = self._render_value(display_url)

        output[ATTR_UPDATE_DATE] = dt_util.utcnow().strftime(DATE_FORMAT)

        return output
