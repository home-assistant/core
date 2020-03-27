"""
Support for interacting with Ais Files.

For more details about this platform, please refer to the documentation at
https://www.ai-speaker.com/
"""
import asyncio
import threading
import os
import logging
import subprocess
from PIL import Image
from aiohttp.web import Request, Response

from homeassistant.components.http import HomeAssistantView
from . import sensor
from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)
IMG_PATH = "/data/data/pl.sviete.dom/files/home/AIS/www/img/"
LOG_PATH_INFO_FILE = "/data/data/pl.sviete.dom/files/home/AIS/.dom/.ais_log_path_info"
DB_PATH_INFO_FILE = "/data/data/pl.sviete.dom/files/home/AIS/.dom/.ais_db_path_info"
LOG_PATH_INFO = None
DB_PATH_INFO = None
G_LOG_PROCESS = None


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

    @asyncio.coroutine
    async def async_change_logger_settings(call):
        await _async_change_logger_settings(hass, call)

    @asyncio.coroutine
    async def async_change_db_settings(call):
        await _async_change_db_settings(hass, call)

    @asyncio.coroutine
    async def async_get_ext_drivers_info(call):
        await _async_get_ext_drivers_info(hass, call)

    hass.services.async_register(DOMAIN, "pick_file", async_pick_file)
    hass.services.async_register(DOMAIN, "refresh_files", async_refresh_files)
    hass.services.async_register(DOMAIN, "remove_file", async_remove_file)
    hass.services.async_register(
        DOMAIN, "change_logger_settings", async_change_logger_settings
    )
    hass.services.async_register(DOMAIN, "change_db_settings", async_change_db_settings)
    hass.services.async_register(
        DOMAIN, "get_ext_drivers_info", async_get_ext_drivers_info
    )

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


async def _async_change_logger_settings(hass, call):
    # on logger change
    global G_LOG_PROCESS
    if "value" not in call.data:
        _LOGGER.error("No value")
        return

    log_drive = call.data["value"]

    hass.async_add_job(
        hass.services.async_call(
            "input_text",
            "set_value",
            {"entity_id": "input_text.ais_logs_path", "value": log_drive},
        )
    )
    # save to file
    await _async_save_log_file_path_info(hass, log_drive)

    # Stop current log process
    if G_LOG_PROCESS is not None:
        _LOGGER.info("terminate log process pid: " + str(G_LOG_PROCESS.pid))
        G_LOG_PROCESS.terminate()
        G_LOG_PROCESS = None

    # check if drive is -
    if log_drive == "-":
        hass.services.async_call(
            "ais_ai_service", "say_it", {"text": "Logowanie do pliku wyłączone"}
        )
        return

    # change log settings
    # Log errors to a file if we have write access to file or config dir
    file_log_path = os.path.abspath(
        "/data/data/pl.sviete.dom/files/home/dom/dyski-wymienne/"
        + log_drive
        + "/ais.log"
    )

    err_path_exists = os.path.isfile(file_log_path)
    err_dir = os.path.dirname(file_log_path)

    # Check if we can write to the error log if it exists or that
    # we can create files in the containing directory if not.
    if (err_path_exists and os.access(file_log_path, os.W_OK)) or (
        not err_path_exists and os.access(err_dir, os.W_OK)
    ):
        command = "pm2 logs >> " + file_log_path
        G_LOG_PROCESS = subprocess.Popen(command, shell=True)
        _LOGGER.info("start log process pid: " + str(G_LOG_PROCESS.pid))
        info = "Logi systemowe zapisywane do pliku log na " + log_drive
    else:
        _LOGGER.error("Unable to set up log %s (access denied)", file_log_path)
        info = "Nie można skonfigurować zapisu do pliku na " + log_drive

    # inform about loging
    hass.async_add_job(
        hass.services.async_call("ais_ai_service", "say_it", {"text": info})
    )
    # re-set log level
    log_level = hass.states.get("input_select.ais_system_logs_level").state
    hass.async_add_job(
        hass.services.async_call("logger", "set_default_level", {"level": log_level})
    )


async def _async_change_db_settings(hass, call):
    # on logger change
    if "value" not in call.data:
        _LOGGER.error("No value")
        return
    hass.async_add_job(
        hass.services.async_call(
            "input_text",
            "set_value",
            {"entity_id": "input_text.ais_db_path", "value": call.data["value"]},
        )
    )
    # save to file
    await _async_save_db_file_path_info(hass, call.data["value"])

    # TODO change db settings


async def _async_get_ext_drivers_info(hass, call):
    # on page load
    log_drive = ""
    db_drive = ""
    if LOG_PATH_INFO is None:
        # get the info from file
        try:
            fptr = open(LOG_PATH_INFO_FILE)
            log_drive = fptr.read().replace("\n", "")
            fptr.close()
        except Exception as e:
            _LOGGER.info("Error get_log_file_path_info " + str(e))
    else:
        log_drive = LOG_PATH_INFO

    if DB_PATH_INFO is None:
        try:
            fptr = open(DB_PATH_INFO_FILE)
            db_drive = fptr.read().replace("\n", "")
            fptr.close()
        except Exception as e:
            _LOGGER.info("Error get_db_file_path_info " + str(e))
    else:
        db_drive = DB_PATH_INFO

    # fill the drives list
    hass.async_add_job(hass.services.async_call("ais_usb", "ls_flash_drives"))

    hass.async_add_job(
        hass.services.async_call(
            "input_text",
            "set_value",
            {"entity_id": "input_text.ais_logs_path", "value": log_drive},
        )
    )

    hass.async_add_job(
        hass.services.async_call(
            "input_text",
            "set_value",
            {"entity_id": "input_text.ais_db_path", "value": db_drive},
        )
    )


async def _async_save_log_file_path_info(hass, path):
    """save status in a file."""
    global LOG_PATH_INFO
    try:
        fptr = open(LOG_PATH_INFO_FILE, "w")
        fptr.write(path)
        fptr.close()
        LOG_PATH_INFO = path
    except Exception as e:
        _LOGGER.error("Error save_db_file_path_info " + str(e))


async def _async_save_db_file_path_info(hass, path):
    """save status in a file."""
    global DB_PATH_INFO
    try:
        fptr = open(DB_PATH_INFO_FILE, "w")
        fptr.write(path)
        fptr.close()
        DB_PATH_INFO = path
    except Exception as e:
        _LOGGER.error("Error save_db_file_path_info " + str(e))

    # inform about downloading
    info = "Zapis zdarzeń do bazy danych wyłączone"
    if path != "":
        info = "Zapis zdarzeń do bazy danych włączony na " + path
    hass.async_add_job(
        hass.services.async_call("ais_ai_service", "say_it", {"text": info})
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
