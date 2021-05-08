"""
Support for interacting with Ais Files.

For more details about this platform, please refer to the documentation at
https://www.ai-speaker.com/
"""
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


async def async_setup(hass, config):
    """Set up the Ais Files platform."""

    # register services
    async def async_transfer_file(call):
        if "path" not in call.data or "name" not in call.data:
            return
        await _async_transfer_file(hass, call.data["path"], call.data["name"])

    async def async_remove_file(call):
        if "path" not in call.data:
            return
        await _async_remove_file(hass, call.data["path"])

    async def async_change_logger_settings(call):
        await _async_change_logger_settings(hass, call)

    hass.services.async_register(DOMAIN, "transfer_file", async_transfer_file)
    hass.services.async_register(DOMAIN, "remove_file", async_remove_file)
    hass.services.async_register(
        DOMAIN, "change_logger_settings", async_change_logger_settings
    )

    hass.http.register_view(FileUpladView)
    hass.http.register_view(FileReadView)
    hass.http.register_view(FileWriteView)
    hass.http.register_view(AisDbConfigView)

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


async def _async_save_logs_settings_info(hass, log_drive, log_level, log_rotating):
    """save log path info in a file."""
    try:
        logs_settings = {
            "logDrive": log_drive,
            "logLevel": log_level,
            "logRotating": log_rotating,
        }
        with open(
            hass.config.config_dir + ais_global.G_LOG_SETTINGS_INFO_FILE, "w"
        ) as outfile:
            json.dump(logs_settings, outfile)
        ais_global.G_LOG_SETTINGS_INFO = logs_settings
    except Exception as e:
        _LOGGER.error("Error save_log_settings_info " + str(e))


async def _async_save_db_settings_info(hass, db_settings):
    """save db url info in a file."""
    try:
        with open(
            hass.config.config_dir + ais_global.G_DB_SETTINGS_INFO_FILE, "w"
        ) as outfile:
            json.dump(db_settings, outfile)
        ais_global.G_DB_SETTINGS_INFO = db_settings
    except Exception as e:
        _LOGGER.error("Error save_db_file_url_info " + str(e))


def resize_image(file_name):
    max_size = 1024
    if file_name.startswith("floorplan"):
        max_size = 1920
    image = Image.open(ais_global.G_AIS_IMG_PATH + file_name)
    original_size = max(image.size[0], image.size[1])

    if original_size >= max_size:
        resized_file = open(ais_global.G_AIS_IMG_PATH + "1024_" + file_name, "wb")
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
        os.remove(ais_global.G_AIS_IMG_PATH + file_name)
        os.rename(
            ais_global.G_AIS_IMG_PATH + "1024_" + file_name,
            ais_global.G_AIS_IMG_PATH + file_name,
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
        with open(ais_global.G_AIS_IMG_PATH + file_name, "wb") as f:
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


class AisDbConfigView(HomeAssistantView):
    """View to save config for the db."""

    requires_auth = False
    url = "/api/ais_file/ais_db_view"
    name = "api:ais_file:ais_db_view"

    def __init__(self):
        """Initialize the view."""
        pass

    async def post(self, request):
        """Handle user login to get gates info."""
        hass = request.app["hass"]
        message = await request.json()
        error_info = ""
        return_info = ""
        db_connection = {
            "dbEngine": message.get("dbEngine", ""),
            "dbDrive": message.get("dbDrive", ""),
            "dbPassword": message.get("dbPassword", ""),
            "dbUser": message.get("dbUser", ""),
            "dbServerIp": message.get("dbServerIp", ""),
            "dbServerName": message.get("dbServerName", ""),
            "dbKeepDays": message.get("dbKeepDays", 10),
            "dbShowLogbook": message.get("dbShowLogbook", False),
            "dbShowHistory": message.get("dbShowHistory", False),
            "dbUrl": "",
        }
        # 1. calculate url
        if (
            db_connection["dbEngine"] is None
            or db_connection["dbEngine"] == "-"
            or db_connection["dbEngine"] == ""
        ):
            db_connection["dbUrl"] = ""
            db_connection["dbDrive"] = "-"
            db_connection["dbPassword"] = ""
            db_connection["dbUser"] = ""
            db_connection["dbServerIp"] = ""
            db_connection["dbServerName"] = ""
            db_connection["dbKeepDays"] = "2"
            db_connection["dbShowLogbook"] = False
            db_connection["dbShowHistory"] = False
            return_info = "Zapis do bazy wyłączony."
        elif db_connection["dbEngine"] == "SQLite (memory)":
            db_connection["dbUrl"] = "sqlite:///:memory:"
            db_connection["dbDrive"] = "-"
            db_connection["dbPassword"] = ""
            db_connection["dbUser"] = ""
            db_connection["dbServerIp"] = ""
            db_connection["dbServerName"] = ""
            db_connection["dbKeepDays"] = "2"
            return_info = "Zapis właczony do bazy w pamięci."
        elif db_connection["dbEngine"] == "SQLite (file)":
            db_connection["dbUrl"] = (
                "sqlite://///data/data/pl.sviete.dom/files/home/dom/dyski-wymienne/"
                + db_connection["dbDrive"]
                + "/ais.db"
            )
            db_connection["dbPassword"] = ""
            db_connection["dbUser"] = ""
            db_connection["dbServerIp"] = ""
            db_connection["dbServerName"] = ""
            # check if dbUrl is valid external drive drive
            from homeassistant.components import ais_usb

            if not ais_usb.is_usb_url_valid_external_drive(db_connection["dbUrl"]):
                error_info = (
                    "Invalid external drive: "
                    + db_connection["dbUrl"]
                    + " selected for recording!"
                )
        else:
            db_user_pass = ""
            if db_connection["dbUser"] + db_connection["dbPassword"] != "":
                db_user_pass = (
                    db_connection["dbUser"] + ":" + db_connection["dbPassword"] + "@"
                )

            if db_connection["dbEngine"] == "MariaDB":
                db_connection["dbUrl"] = (
                    "mysql+pymysql://"
                    + db_user_pass
                    + db_connection["dbServerIp"]
                    + "/"
                    + db_connection["dbServerName"]
                    + "?charset=utf8mb4"
                )
            elif db_connection["dbEngine"] == "MySQL":
                db_connection["dbUrl"] = (
                    "mysql://"
                    + db_user_pass
                    + db_connection["dbServerIp"]
                    + "/"
                    + db_connection["dbServerName"]
                    + "?charset=utf8mb4"
                )
            elif db_connection["dbEngine"] == "PostgreSQL":
                db_connection["dbUrl"] = (
                    "postgresql://"
                    + db_user_pass
                    + db_connection["dbServerIp"]
                    + "/"
                    + db_connection["dbServerName"]
                )

        # 2. check the connection
        if error_info == "" and return_info == "":
            """Ensure database is ready to fly."""
            kwargs = {}
            if "sqlite" in db_connection["dbUrl"]:
                kwargs["connect_args"] = {"check_same_thread": False}
                kwargs["poolclass"] = StaticPool
                kwargs["pool_reset_on_return"] = None
            else:
                kwargs["echo"] = False
            try:
                engine = create_engine(db_connection["dbUrl"], **kwargs)
                with engine.connect() as connection:
                    result = connection.execute("SELECT 1")
                    for row in result:
                        _LOGGER.info("SELECT 1: " + str(row))

                return_info = (
                    "Zapis do bazy " + db_connection["dbEngine"] + " skonfigurowany."
                )
            except Exception as e:
                _LOGGER.error("Exception:" + str(e))
                error_info = "Błąd konfiguracji zapisu do bazy " + str(e)

        # 3. store the settings in session and file
        if error_info == "":
            await _async_save_db_settings_info(hass, db_connection)
            hass.states.async_set(
                "sensor.ais_db_connection_info", "db_url_saved", db_connection
            )

        # 4. hide / show panels
        panel_history = "history" in hass.data.get(
            hass.components.frontend.DATA_PANELS, {}
        )
        panel_logbook = "logbook" in hass.data.get(
            hass.components.frontend.DATA_PANELS, {}
        )
        # History
        if db_connection["dbShowHistory"]:
            return_info += " Historia włączona."

            if not panel_history:
                hass.components.frontend.async_register_built_in_panel(
                    "history", "history", "hass:poll-box"
                )
        else:
            return_info += " Historia wyłączona."
            if panel_history:
                hass.components.frontend.async_remove_panel("history")

        # Logbook
        if db_connection["dbShowLogbook"]:
            return_info += "Dziennik włączony."
            if not panel_logbook:
                hass.components.frontend.async_register_built_in_panel(
                    "logbook", "logbook", "hass:format-list-bulleted-type"
                )
        else:
            return_info += "Dziennik wyłączony."
            if panel_logbook:
                hass.components.frontend.async_remove_panel("logbook")

        return self.json({"info": return_info, "error": error_info})
