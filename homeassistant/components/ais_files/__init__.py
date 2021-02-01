"""
Support for interacting with Ais Files.

For more details about this platform, please refer to the documentation at
https://www.ai-speaker.com/
"""
import asyncio
import json
import logging
import os

from PIL import Image
from aiohttp.web import FileResponse, Request, Response
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import homeassistant.components.ais_dom.ais_global as ais_global
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import HTTP_BAD_REQUEST

from . import sensor
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
IMG_PATH = "/data/data/pl.sviete.dom/files/home/AIS/www/img/"
G_LOG_SETTINGS_INFO_FILE = "/.dom/.ais_log_settings_info"
G_DB_SETTINGS_INFO_FILE = "/.dom/.ais_db_settings_info"


@asyncio.coroutine
async def async_setup(hass, config):
    """Set up the Ais Files platform."""

    # register services
    @asyncio.coroutine
    async def async_transfer_file(call):
        if "path" not in call.data or "name" not in call.data:
            return
        await _async_transfer_file(hass, call.data["path"], call.data["name"])

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
    async def async_get_db_log_settings_info(call):
        await _async_get_db_log_settings_info(hass, call)

    @asyncio.coroutine
    async def async_check_db_connection(call):
        await _async_check_db_connection(hass, call)

    hass.services.async_register(DOMAIN, "pick_file", async_pick_file)
    hass.services.async_register(DOMAIN, "refresh_files", async_refresh_files)
    hass.services.async_register(DOMAIN, "transfer_file", async_transfer_file)
    hass.services.async_register(DOMAIN, "remove_file", async_remove_file)
    hass.services.async_register(
        DOMAIN, "change_logger_settings", async_change_logger_settings
    )
    hass.services.async_register(
        DOMAIN, "check_db_connection", async_check_db_connection
    )
    hass.services.async_register(
        DOMAIN, "get_db_log_settings_info", async_get_db_log_settings_info
    )

    hass.http.register_view(FileUpladView)
    hass.http.register_view(FileReadView)
    hass.http.register_view(FileWriteView)

    return True


# transfer file from HASS upload folder to ais gallery
async def _async_transfer_file(hass, path, name):
    # remove file from hass image folder
    path = path.replace("/api/image/serve/", "")
    path = path.replace("/512x512", "")
    import shutil

    # 1. transfer
    shutil.copy(
        hass.config.config_dir + "/image/" + path + "/original",
        hass.config.config_dir + "/www/img/" + name + ".jpeg",
    )
    # 2. remove
    shutil.rmtree(hass.config.config_dir + "/image/" + path)

    await _async_refresh_files(hass)


async def _async_remove_file(hass, path):
    if "api/image/serve" in path:
        # remove file from hass image folder
        path = path.replace("/api/image/serve/", "")
        path = path.replace("/512x512", "")
        import shutil

        try:
            shutil.rmtree(hass.config.config_dir + "/image/" + path)
        except Exception as e:
            pass

    else:
        # remove file from ais folder
        path = path.replace("/local/", "/data/data/pl.sviete.dom/files/home/AIS/www/")
        path = path.replace(
            "/media/galeria/", "/data/data/pl.sviete.dom/files/home/AIS/www/img/"
        ).split("?authSig")[0]
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
    if "log_drive" not in call.data:
        _LOGGER.error("No log_drive")
        return
    if "log_level" not in call.data:
        _LOGGER.error("No log_level")
        return
    log_rotating = 10
    if "log_rotating" in call.data:
        log_rotating = call.data["log_rotating"]

    log_drive = call.data["log_drive"]
    log_level = call.data["log_level"]

    chaged_settings = "log_drive"
    # check what was changed
    if ais_global.G_LOG_SETTINGS_INFO is None:
        chaged_settings = "log_drive"
    else:
        if (
            "logDrive" in ais_global.G_LOG_SETTINGS_INFO
            and ais_global.G_LOG_SETTINGS_INFO["logDrive"] != log_drive
        ):
            chaged_settings = "log_drive"
        elif (
            "logLevel" in ais_global.G_LOG_SETTINGS_INFO
            and ais_global.G_LOG_SETTINGS_INFO["logLevel"] != log_level
        ):
            chaged_settings = "log_level"
        elif (
            "logRotating" in ais_global.G_LOG_SETTINGS_INFO
            and ais_global.G_LOG_SETTINGS_INFO["logRotating"] != log_rotating
        ):
            chaged_settings = "log_rotating"

    # store settings in file
    await _async_save_logs_settings_info(hass, log_drive, log_level, log_rotating)

    # set the logs settings info
    hass.states.async_set(
        "sensor.ais_logs_settings_info",
        "0",
        {"logDrive": log_drive, "logLevel": log_level, "logRotating": log_rotating},
    )

    if chaged_settings == "log_drive":
        # check if drive is - then remove logging to file
        if log_drive == "-":
            info = "Logowanie do pliku wyłączone"
        else:
            # change log settings
            log_file = (
                ais_global.G_REMOTE_DRIVES_DOM_PATH + "/" + log_drive + "/ais.log"
            )
            # Log errors to a file if we have write access to file or dir
            err_log_path = os.path.abspath(log_file)
            err_path_exists = os.path.isfile(err_log_path)
            # check if this is correct external drive
            from homeassistant.components import ais_usb

            err_path_is_external_drive = ais_usb.is_usb_url_valid_external_drive(
                err_log_path
            )
            err_dir = os.path.dirname(err_log_path)

            # Check if we can write to the error log if it exists or that
            # we can create files in the containing directory if not.
            if err_path_is_external_drive and (
                (err_path_exists and os.access(err_log_path, os.W_OK))
                or (not err_path_exists and os.access(err_dir, os.W_OK))
            ):
                info = "Logi systemowe zapisywane do pliku log na " + log_drive

                hass.states.async_set(
                    "sensor.ais_logs_settings_info",
                    "1",
                    {
                        "logDrive": log_drive,
                        "logLevel": log_level,
                        "logRotating": log_rotating,
                        "logError": "",
                    },
                )
            else:
                log_error = "Unable to set up log " + log_file + " (access denied)"
                _LOGGER.error(log_error)
                info = "Nie można skonfigurować zapisu do pliku na " + log_drive
                hass.states.async_set(
                    "sensor.ais_logs_settings_info",
                    "0",
                    {
                        "logDrive": log_drive,
                        "logLevel": log_level,
                        "logRotating": log_rotating,
                        "logError": log_error,
                    },
                )

    elif chaged_settings == "log_level":
        info = "Poziom logowania " + log_level
        hass.async_add_job(
            hass.services.async_call(
                "logger", "set_default_level", {"level": log_level}
            )
        )
    elif chaged_settings == "log_rotating":
        info = "Rotacja logów co " + str(log_rotating) + " dni"

    # inform about loging
    hass.async_add_job(
        hass.services.async_call("ais_ai_service", "say_it", {"text": info})
    )


async def _async_check_db_connection(hass, call):
    # on logger change
    buttonClick = call.data["buttonClick"]
    if buttonClick is False:
        # reset conn info after change in app
        hass.states.async_set(
            "sensor.ais_db_connection_info", "db_url_not_valid", call.data
        )
        return

    # check db connection info to know the step
    ais_db_connection_info = hass.states.get("sensor.ais_db_connection_info")
    state = ais_db_connection_info.state
    attributes = ais_db_connection_info.attributes
    db_connection = {
        "dbEngine": attributes.get("dbEngine", ""),
        "dbDrive": attributes.get("dbDrive", ""),
        "dbUrl": attributes.get("dbUrl", ""),
        "dbPassword": attributes.get("dbPassword", ""),
        "dbUser": attributes.get("dbUser", ""),
        "dbServerIp": attributes.get("dbServerIp", ""),
        "dbServerName": attributes.get("dbServerName", ""),
        "dbKeepDays": attributes.get("dbKeepDays", 10),
        "errorInfo": attributes.get("errorInfo", ""),
    }
    if state in ("no_db_url_saved", "db_url_not_valid"):
        # buttonName = "Sprawdź połączenie";
        """Ensure database is ready to fly."""
        kwargs = {}
        if "sqlite" in db_connection["dbUrl"]:
            kwargs["connect_args"] = {"check_same_thread": False}
            kwargs["poolclass"] = StaticPool
            kwargs["pool_reset_on_return"] = None
        else:
            kwargs["echo"] = False
        try:
            # check if dbUrl is valid external drive drive
            if db_connection["dbUrl"].startswith("sqlite://///"):
                # DB in file
                from homeassistant.components import ais_usb

                if (
                    ais_usb.is_usb_url_valid_external_drive(db_connection["dbUrl"])
                    is not True
                ):
                    error_info = (
                        "Invalid external drive: "
                        + db_connection["dbUrl"]
                        + " selected for recording!"
                    )

                    _LOGGER.error(error_info)
                    db_connection["errorInfo"] = error_info
                    hass.states.async_set(
                        "sensor.ais_db_connection_info",
                        "db_url_not_valid",
                        db_connection,
                    )
                    return
            engine = create_engine(db_connection["dbUrl"], **kwargs)
            with engine.connect() as connection:
                result = connection.execute("SELECT 1")
                for row in result:
                    _LOGGER.info("SELECT 1: " + str(row))
                hass.states.async_set(
                    "sensor.ais_db_connection_info", "db_url_valid", db_connection
                )
        except Exception as e:
            _LOGGER.error("Exception:" + str(e))
            db_connection["errorInfo"] = str(e)
            hass.states.async_set(
                "sensor.ais_db_connection_info", "db_url_not_valid", db_connection
            )
    elif state == "db_url_valid":
        # buttonName = "Zapisz połączenie";
        # save to file
        await _async_save_db_settings_info(hass, db_connection)

        hass.states.async_set(
            "sensor.ais_db_connection_info", "db_url_saved", db_connection
        )

    elif state == "db_url_saved":
        # buttonName = "Usuń polączenie";
        # save to file
        await _async_save_db_settings_info(hass, {})

        hass.states.async_set(
            "sensor.ais_db_connection_info",
            "no_db_url_saved",
            {"dbUrl": "", "dbDrive": "-", "dbEngine": "-"},
        )


async def _async_get_db_log_settings_info(hass, call):
    on_system_start = False
    if "on_system_start" in call.data:
        on_system_start = True
    # on page load
    log_settings = {}
    db_settings = {}
    if ais_global.G_LOG_SETTINGS_INFO is None:
        # get the info from file
        try:
            with open(hass.config.config_dir + G_LOG_SETTINGS_INFO_FILE) as json_file:
                log_settings = json.load(json_file)
            ais_global.G_LOG_SETTINGS_INFO = log_settings
        except Exception as e:
            _LOGGER.info("Error get log settings info " + str(e))
    else:
        log_settings = ais_global.G_LOG_SETTINGS_INFO

    if ais_global.G_DB_SETTINGS_INFO is None:
        try:
            with open(hass.config.config_dir + G_DB_SETTINGS_INFO_FILE) as json_file:
                db_settings = json.load(json_file)
            ais_global.G_DB_SETTINGS_INFO = db_settings
            if "dbKeepDays" not in ais_global.G_DB_SETTINGS_INFO:
                ais_global.G_DB_SETTINGS_INFO["dbKeepDays"] = 10
        except Exception as e:
            _LOGGER.info("Error get db settings info " + str(e))
    else:
        db_settings = ais_global.G_DB_SETTINGS_INFO

    # fill the drives list
    hass.async_add_job(hass.services.async_call("ais_usb", "ls_flash_drives"))

    # set the logs settings info
    if ais_global.G_LOG_SETTINGS_INFO is not None:
        hass.states.async_set("sensor.ais_logs_settings_info", "1", log_settings)
        # enable logs on system start (if set)
        if on_system_start:
            # re-set log level
            hass.async_add_job(
                hass.services.async_call(
                    "logger",
                    "set_default_level",
                    {"level": ais_global.G_LOG_SETTINGS_INFO["logLevel"]},
                )
            )
    else:
        hass.states.async_set("sensor.ais_logs_settings_info", "0", log_settings)

    # set the db settings sensor info
    # step - no db url saved
    db_conn_step = "no_db_url_saved"
    if "dbUrl" in db_settings:
        db_conn_step = "db_url_saved"

    if db_conn_step == "no_db_url_saved" and hass.services.has_service(
        "recorder", "purge"
    ):
        # the recorder was enabled via other integration
        db_settings["errorInfo"] = "Rekorder włączony przez inny komponent!"
        db_settings["dbEngine"] = "SQLite (memory)"

    hass.states.async_set("sensor.ais_db_connection_info", db_conn_step, db_settings)


async def _async_save_logs_settings_info(hass, log_drive, log_level, log_rotating):
    """save log path info in a file."""
    try:
        logs_settings = {
            "logDrive": log_drive,
            "logLevel": log_level,
            "logRotating": log_rotating,
        }
        with open(hass.config.config_dir + G_LOG_SETTINGS_INFO_FILE, "w") as outfile:
            json.dump(logs_settings, outfile)
        ais_global.G_LOG_SETTINGS_INFO = logs_settings
    except Exception as e:
        _LOGGER.error("Error save_log_settings_info " + str(e))


async def _async_save_db_settings_info(hass, db_settings):
    """save db url info in a file."""
    try:
        with open(hass.config.config_dir + G_DB_SETTINGS_INFO_FILE, "w") as outfile:
            json.dump(db_settings, outfile)
        ais_global.G_DB_SETTINGS_INFO = db_settings
    except Exception as e:
        _LOGGER.error("Error save_db_file_url_info " + str(e))


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


class FileReadView(HomeAssistantView):
    """View to fetch the file."""

    url = "/api/ais_file/read"
    name = "api:ais_file:read"

    async def post(self, request):
        """Retrieve the file."""
        try:
            data = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON", HTTP_BAD_REQUEST)
        file_path = data["filePath"]
        if file_path == "/data/data/pl.sviete.dom/files/home/AIS/ais_welcome.txt":
            if not os.path.isfile(file_path):
                # create empty file
                os.mknod(file_path)
        response = FileResponse(path=file_path)
        return response


class FileWriteView(HomeAssistantView):
    """View to write the file."""

    url = "/api/ais_file/write"
    name = "api:ais_file:write"

    async def post(self, request):
        """Retrieve the file."""
        try:
            data = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON", HTTP_BAD_REQUEST)

        file_path = data["filePath"]
        file_body = data["fileBody"]

        with open(file_path, "w") as f:
            f.write(file_body)
            f.close()
