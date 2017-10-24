"""
Support for Alexa skill service end point.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/alexa/
"""
import copy
import logging
from datetime import datetime
import uuid

from homeassistant.core import callback
from homeassistant.helpers import template
from homeassistant.components import http

from .const import (
    CONF_UID, CONF_TITLE, CONF_AUDIO, CONF_TEXT, CONF_DISPLAY_URL, ATTR_UID,
    ATTR_UPDATE_DATE, ATTR_TITLE_TEXT, ATTR_STREAM_URL, ATTR_MAIN_TEXT,
    ATTR_REDIRECTION_URL, DATE_FORMAT)


_LOGGER = logging.getLogger(__name__)

FLASH_BRIEFINGS_API_ENDPOINT = '/api/alexa/flash_briefings/{briefing_id}'


@callback
def async_setup(hass, flash_briefing_config):
    """Activate Alexa component."""
    hass.http.register_view(
        AlexaFlashBriefingView(hass, flash_briefing_config))


class AlexaFlashBriefingView(http.HomeAssistantView):
    """Handle Alexa Flash Briefing skill requests."""

    url = FLASH_BRIEFINGS_API_ENDPOINT
    name = 'api:alexa:flash_briefings'

    def __init__(self, hass, flash_briefings):
        """Initialize Alexa view."""
        super().__init__()
        self.flash_briefings = copy.deepcopy(flash_briefings)
        template.attach(hass, self.flash_briefings)

    @callback
    def get(self, request, briefing_id):
        """Handle Alexa Flash Briefing request."""
        _LOGGER.debug('Received Alexa flash briefing request for: %s',
                      briefing_id)

        if self.flash_briefings.get(briefing_id) is None:
            err = 'No configured Alexa flash briefing was found for: %s'
            _LOGGER.error(err, briefing_id)
            return b'', 404

        briefing = []

        for item in self.flash_briefings.get(briefing_id, []):
            output = {}
            if item.get(CONF_TITLE) is not None:
                if isinstance(item.get(CONF_TITLE), template.Template):
                    output[ATTR_TITLE_TEXT] = item[CONF_TITLE].async_render()
                else:
                    output[ATTR_TITLE_TEXT] = item.get(CONF_TITLE)

            if item.get(CONF_TEXT) is not None:
                if isinstance(item.get(CONF_TEXT), template.Template):
                    output[ATTR_MAIN_TEXT] = item[CONF_TEXT].async_render()
                else:
                    output[ATTR_MAIN_TEXT] = item.get(CONF_TEXT)

            uid = item.get(CONF_UID)
            if uid is None:
                uid = str(uuid.uuid4())
            output[ATTR_UID] = uid

            if item.get(CONF_AUDIO) is not None:
                if isinstance(item.get(CONF_AUDIO), template.Template):
                    output[ATTR_STREAM_URL] = item[CONF_AUDIO].async_render()
                else:
                    output[ATTR_STREAM_URL] = item.get(CONF_AUDIO)

            if item.get(CONF_DISPLAY_URL) is not None:
                if isinstance(item.get(CONF_DISPLAY_URL),
                              template.Template):
                    output[ATTR_REDIRECTION_URL] = \
                        item[CONF_DISPLAY_URL].async_render()
                else:
                    output[ATTR_REDIRECTION_URL] = item.get(CONF_DISPLAY_URL)

            output[ATTR_UPDATE_DATE] = datetime.now().strftime(DATE_FORMAT)

            briefing.append(output)

        return self.json(briefing)
