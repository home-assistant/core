"""
Support for interacting with Ais Files.

For more details about this platform, please refer to the documentation at
https://sviete.github.io/AIS-docs
"""
import logging
import asyncio
import os
from homeassistant.components.http import HomeAssistantView
from aiohttp.web import Request, Response

from . import sensor
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
async def async_setup(hass, config):
    """Set up the Ais Files platform."""

    # register services
    @asyncio.coroutine
    async def async_remove_file(call):
        if "path" not in call.data:
            return
        await _async_remove_file(hass, call.data["path"])

    @asyncio.coroutine
    async def async_refresh_files(call):
        await _async_refresh_files(hass)

    hass.services.async_register(DOMAIN, "refresh_files", async_refresh_files)
    hass.services.async_register(DOMAIN, "remove_file", async_remove_file)

    hass.http.register_view(FileUpladView)

    return True


async def _async_remove_file(hass, path):
    path = path.replace("/local/", "/data/data/pl.sviete.dom/files/home/AIS/www/")
    os.remove(path)
    await _async_refresh_files(hass)


async def _async_refresh_files(hass):
    # refresh sensor after file was added or deleted
    hass.async_add_job(
        hass.services.async_call(
            "homeassistant", "update_entity", {"entity_id": "sensor.ais_gallery_img"}
        )
    )


class FileUpladView(HomeAssistantView):
    """A view that accepts file upload requests."""

    url = "/api/ais_file/upload"
    name = "api:ais_file:uplad"

    async def post(self, request: Request) -> Response:
        """Handle the POST request for upload file."""
        data = await request.post()
        file = data["file"]
        file_name = file.filename
        file_data = file.file.read()
        with open(
            "/data/data/pl.sviete.dom/files/home/AIS/www/img/" + file_name, "wb"
        ) as f:
            f.write(file_data)
            f.close()

        hass = request.app["hass"]
        hass.async_add_job(hass.services.async_call(DOMAIN, "refresh_files"))
