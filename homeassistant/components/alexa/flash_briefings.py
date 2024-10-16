"""Support for Alexa skill service end point."""

import hmac
from http import HTTPStatus
import logging
from typing import Any, Optional
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
    def get(
        self, request: http.HomeAssistantRequest, briefing_id: str
    ) -> StreamResponse | tuple[bytes, HTTPStatus]:
        """Handle Alexa Flash Briefing request."""
        _LOGGER.debug("Received Alexa flash briefing request for: %s", briefing_id)

        if not self._validate_password(request.query.get(API_PASSWORD), briefing_id):
            return b"", HTTPStatus.UNAUTHORIZED

        if not isinstance(self.flash_briefings.get(briefing_id), list):
            _LOGGER.error(
                "No configured Alexa flash briefing was found for: %s", briefing_id
            )
            return b"", HTTPStatus.NOT_FOUND

        briefing = [
            self._process_briefing_item(item)
            for item in self.flash_briefings.get(briefing_id, [])
        ]

        return self.json(briefing)

    def _validate_password(
        self, request_password: str | None, briefing_id: str
    ) -> bool:
        """Validate the provided password."""
        if request_password is None:
            _LOGGER.error(
                "No password provided for Alexa flash briefing: %s", briefing_id
            )
            return False

        if not hmac.compare_digest(
            request_password.encode("utf-8"),
            self.flash_briefings[CONF_PASSWORD].encode("utf-8"),
        ):
            _LOGGER.error("Wrong password for Alexa flash briefing: %s", briefing_id)
            return False

        return True

    def _process_briefing_item(self, item: dict) -> dict:
        """Process a single flash briefing item."""
        return {
            ATTR_TITLE_TEXT: self._render_or_get(item.get(CONF_TITLE)),
            ATTR_MAIN_TEXT: self._render_or_get(item.get(CONF_TEXT)),
            ATTR_UID: item.get(CONF_UID, str(uuid.uuid4())),
            ATTR_STREAM_URL: self._render_or_get(item.get(CONF_AUDIO)),
            ATTR_REDIRECTION_URL: self._render_or_get(item.get(CONF_DISPLAY_URL)),
            ATTR_UPDATE_DATE: dt_util.utcnow().strftime(DATE_FORMAT),
        }


    def _render_or_get(self, value: Any) -> Any | None:
        """Render a template or return the value as-is."""
        if value is None:
            return None
        if isinstance(value, template.Template):
            return value.async_render(parse_result=False)
        return value

