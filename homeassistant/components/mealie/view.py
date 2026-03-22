"""Implement a view to provide proxied Mealie recipe images."""

from __future__ import annotations

from http import HTTPStatus
import logging

from aiohttp import ClientError, web
from aiohttp.hdrs import AUTHORIZATION, CACHE_CONTROL
from aiohttp.typedefs import LooseHeaders

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, MEALIE_IMAGE_PROXY_PATH
from .utils import mealie_recipe_image_url

_LOGGER = logging.getLogger(__name__)


class MealieImageView(HomeAssistantView):
    """View to serve a proxied Mealie recipe image."""

    name = "api:mealie:image"
    url = f"{MEALIE_IMAGE_PROXY_PATH}/{{entry_id}}/{{recipe_id}}"
    requires_auth = False

    async def get(
        self,
        request: web.Request,
        entry_id: str,
        recipe_id: str,
    ) -> web.Response:
        """Return a proxied recipe image from Mealie."""
        hass = request.app[KEY_HASS]

        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            _LOGGER.warning("Image proxy request for unknown config entry %s", entry_id)
            return web.Response(status=HTTPStatus.NOT_FOUND)

        host = entry.data[CONF_HOST]
        token = entry.data[CONF_API_TOKEN]
        image_url = mealie_recipe_image_url(host, recipe_id)
        _LOGGER.debug("Fetching Mealie image from %s", image_url)

        session = async_get_clientsession(
            hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, True)
        )
        try:
            async with session.get(
                image_url,
                headers={AUTHORIZATION: f"Bearer {token}"},
            ) as response:
                if response.status != HTTPStatus.OK:
                    return web.Response(status=HTTPStatus.NOT_FOUND)
                data = await response.read()
                content_type = response.headers.get("Content-Type", "image/webp")
                headers: LooseHeaders = {CACHE_CONTROL: "max-age=3600"}
                return web.Response(
                    body=data, content_type=content_type, headers=headers
                )
        except ClientError:
            _LOGGER.exception("Error fetching Mealie image for recipe %s", recipe_id)
            return web.Response(status=HTTPStatus.SERVICE_UNAVAILABLE)
