"""
Support for interacting with Ais Files.

For more details about this platform, please refer to the documentation at
https://www.ai-speaker.com/
"""
import asyncio
import logging
import os

from PIL import Image
from aiohttp.web import Request, Response

from homeassistant.components.http import HomeAssistantView

from . import sensor
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
IMG_PATH = "/data/data/pl.sviete.dom/files/home/AIS/www/img/"


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

    @asyncio.coroutine
    async def async_pick_file(call):
        if "idx" not in call.data:
            return
        await _async_pick_file(hass, call.data["idx"])

    hass.services.async_register(DOMAIN, "pick_file", async_pick_file)
    hass.services.async_register(DOMAIN, "refresh_files", async_refresh_files)
    hass.services.async_register(DOMAIN, "remove_file", async_remove_file)

    hass.http.register_view(FileUpladView)

    return True


async def _async_remove_file(hass, path):
    path = path.replace("/local/", "/data/data/pl.sviete.dom/files/home/AIS/www/")
    os.remove(path)
    await _async_refresh_files(hass)
    await _async_pick_file(hass, 0)


async def _async_pick_file(hass, idx):
    state = hass.states.get("sensor.ais_gallery_img")
    attr = state.attributes
    hass.states.async_set("sensor.ais_gallery_img", idx, attr)


async def _async_refresh_files(hass):
    # refresh sensor after file was added or deleted
    hass.async_add_job(
        hass.services.async_call(
            "homeassistant", "update_entity", {"entity_id": "sensor.ais_gallery_img"}
        )
    )


def resize_image(file_name):
    max_size = 1024
    if file_name.startswith("floorplan"):
        max_size = 1920
    image = Image.open(IMG_PATH + file_name)
    original_size = max(image.size[0], image.size[1])

    if original_size >= max_size:
        resized_file = open(IMG_PATH + "1024_" + file_name, "wb")
        if image.size[0] > image.size[1]:
            resized_width = max_size
            resized_height = int(
                round((max_size / float(image.size[0])) * image.size[1])
            )
        else:
            resized_height = max_size
            resized_width = int(
                round((max_size / float(image.size[1])) * image.size[0])
            )

        image = image.resize((resized_width, resized_height), Image.ANTIALIAS)
        image.save(resized_file)
        os.remove(IMG_PATH + file_name)
        os.rename(IMG_PATH + "1024_" + file_name, IMG_PATH + file_name)


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
        with open(IMG_PATH + file_name, "wb") as f:
            f.write(file_data)
            f.close()
        # resize the file
        if file_name.endswith(".svg") is False:
            resize_image(file_name)
        hass = request.app["hass"]
        hass.async_add_job(hass.services.async_call(DOMAIN, "refresh_files"))
        hass.async_add_job(hass.services.async_call(DOMAIN, "pick_file", {"idx": 0}))
