"""iOS app specific logic."""
import logging
from aiohttp.web import json_response

from homeassistant.helpers import template

_LOGGER = logging.getLogger(__name__)
WEBHOOK_TYPE_RENDER_COMPLICATIONS = 'render_complications'


async def async_handle_webhook_message(hass, device, webhook_type, data):
    """Return a webhook response for the given arguments."""
    _LOGGER.info("iOS: received msg %s %s %s", webhook_type, device, data)

    if webhook_type == WEBHOOK_TYPE_RENDER_COMPLICATIONS:
        resp = {}
        for family, templates in data['templates'].items():
            resp[family] = {}
            for key, tpl in templates.items():
                rendered = template.Template(tpl, hass).async_render()
                resp[family][key] = rendered
        return json_response(resp)
