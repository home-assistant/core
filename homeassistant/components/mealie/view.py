"""Implement a view to provide proxied Mealie recipe images."""

from __future__ import annotations

from http import HTTPStatus

import aiohttp
from aiohttp import ClientError, web
from aiohttp.hdrs import AUTHORIZATION, CACHE_CONTROL
from aiohttp.typedefs import LooseHeaders

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER as _LOGGER, MEALIE_IMAGE_PROXY_PATH
from .utils import mealie_recipe_image_url

_IMAGE_PROXY_TIMEOUT = aiohttp.ClientTimeout(total=10)
_ALLOWED_CONTENT_TYPES = frozenset({"image/webp", "image/jpeg", "image/png"})
_MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MiB


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
            _LOGGER.debug("Image proxy request for unknown config entry %s", entry_id)
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
                timeout=_IMAGE_PROXY_TIMEOUT,
            ) as response:
                if response.status != HTTPStatus.OK:
                    return web.Response(status=HTTPStatus.NOT_FOUND)
                content_type = response.content_type
                if content_type not in _ALLOWED_CONTENT_TYPES:
                    _LOGGER.warning(
                        "Unexpected content-type %r from Mealie for recipe %s",
                        content_type,
                        recipe_id,
                    )
                    return web.Response(status=HTTPStatus.BAD_GATEWAY)
                content_length_str = response.headers.get("Content-Length")
                if content_length_str is not None:
                    try:
                        if int(content_length_str) > _MAX_IMAGE_SIZE:
                            return web.Response(status=HTTPStatus.BAD_GATEWAY)
                    except ValueError:
                        pass
                data = await response.read()
                if len(data) > _MAX_IMAGE_SIZE:
                    return web.Response(status=HTTPStatus.BAD_GATEWAY)
                headers: LooseHeaders = {CACHE_CONTROL: "max-age=3600"}
                return web.Response(
                    body=data, content_type=content_type, headers=headers
                )
        except (ClientError, TimeoutError) as err:
            _LOGGER.warning(
                "Error fetching Mealie image for recipe %s from %s: %s",
                recipe_id,
                image_url,
                err,
            )
            return web.Response(status=HTTPStatus.SERVICE_UNAVAILABLE)
