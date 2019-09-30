"""
Support to check for available updates.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/updater/
"""
import asyncio
from distutils.version import StrictVersion
import json
import logging
import os
import platform
import uuid
import sys

import aiohttp
import async_timeout
import voluptuous as vol

from subprocess import PIPE, Popen
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.const import __version__ as current_version
from homeassistant.helpers import event
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.ais_dom import ais_global
from homeassistant.components import ais_cloud

aisCloud = ais_cloud.AisCloudWS()

_LOGGER = logging.getLogger(__name__)

ATTR_RELEASE_NOTES = "release_notes"

CONF_REPORTING = "reporting"
CONF_COMPONENT_REPORTING = "include_used_components"

DOMAIN = "ais_updater"
SERVICE_CHECK_VERSION = "check_version"
SERVICE_UPGRADE_PACKAGE = "upgrade_package"
SERVICE_EXECUTE_UPGRADE = "execute_upgrade"
SERVICE_DOWNLOAD_UPGRADE = "download_upgrade"
ENTITY_ID = "sensor.version_info"
ATTR_UPDATE_STATUS = "update_status"
ATTR_UPDATE_CHECK_TIME = "update_check_time"

UPDATE_STATUS_CHECKING = "checking"
UPDATE_STATUS_OUTDATED = "outdated"
UPDATE_STATUS_DOWNLOADING = "downloading"
UPDATE_STATUS_INSTALLING = "installing"
UPDATE_STATUS_UPDATED = "updated"
UPDATE_STATUS_UNKNOWN = "unknown"

UPDATER_URL = "https://powiedz.co/ords/dom/dom/updater_new"
UPDATER_STATUS_FILE = ".update_status"
G_CURRENT_ANDROID_VERSION = "0"
G_CURRENT_LINUX_VERSION = "0"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            vol.Optional(CONF_REPORTING, default=True): cv.boolean,
            vol.Optional(CONF_COMPONENT_REPORTING, default=False): cv.boolean,
        }
    },
    extra=vol.ALLOW_EXTRA,
)


def _set_update_status(hass, status):
    """save status in a file."""
    with open(hass.config.path(UPDATER_STATUS_FILE), "w") as fptr:
        fptr.write(status)

    state = hass.states.get(ENTITY_ID)
    attr = state.attributes
    new_attr = attr.copy()
    info = ""
    if status == UPDATE_STATUS_DOWNLOADING:
        info = "Pobieram aktualizacje"
    elif status == UPDATE_STATUS_INSTALLING:
        info = "Instaluje aktualizacje"
    new_attr[ATTR_UPDATE_STATUS] = status
    new_attr[ATTR_UPDATE_CHECK_TIME] = get_current_dt()
    hass.states.async_set(ENTITY_ID, info, new_attr)


def _get_status_from_file(hass):
    """Load status from a file or return None."""
    try:
        with open(hass.config.path(UPDATER_STATUS_FILE)) as fptr:
            status = fptr.read().replace("\n", "")
            return status
    except Exception as e:
        _LOGGER.error("Error get_status_from_file " + str(e))
        return None


async def async_setup(hass, config):
    """Set up the updater component."""

    config = config.get(DOMAIN, {})
    include_components = config.get(CONF_COMPONENT_REPORTING)

    async def check_new_version(now):
        say_it = False
        # check if we have datetime.datetime or call.data object
        if type(now) == "ServiceCall":
            if "say" in now.data:
                say_it = now.data["say"]
        """Check if a new version is available and report if one is."""
        auto_update = hass.states.get("input_boolean.ais_auto_update").state
        result = await get_newest_version(hass, include_components, auto_update)

        if result is None:
            return

        need_to_update, dom_app_newest_version, release_notes = result

        # Validate version
        if need_to_update:
            _LOGGER.info("The latest available version is %s", dom_app_newest_version)
            if auto_update:
                info = "Aktualizuje system do najnowszej wersji. " + release_notes
            else:
                info = "Dostępna jest aktualizacja. " + release_notes

            hass.states.async_set(
                "script.ais_update_system",
                "off",
                {
                    ATTR_FRIENDLY_NAME: " Zainstaluj aktualizację",
                    "icon": "mdi:download",
                },
            )

            # notify about update
            if auto_update:
                hass.components.persistent_notification.async_create(
                    title="Aktualizuje system do najnowszej wersji ",
                    message=(
                        info + "[ Status aktualizacji](/config/ais_dom_config_update)"
                    ),
                    notification_id="ais_update_notification",
                )
            else:
                hass.components.persistent_notification.async_create(
                    title="Dostępna jest aktualizacja ",
                    message=(
                        info
                        + "[ Przejdź, by zainstalować](/config/ais_dom_config_update)"
                    ),
                    notification_id="ais_update_notification",
                )

            # say info about update
            import homeassistant.components.ais_ai_service as ais_ai

            if say_it or (
                ais_ai.CURR_ENTITIE == "script.ais_update_system"
                and ais_ai.CURR_BUTTON_CODE == 23
            ):
                await hass.services.async_call(
                    "ais_ai_service", "say_it", {"text": info}
                )
            else:
                if ais_global.G_AIS_START_IS_DONE:
                    await hass.services.async_call(
                        "ais_ai_service", "say_it", {"text": info}
                    )
        else:
            # dismiss update notification
            hass.components.persistent_notification.async_dismiss(
                "ais_update_notification"
            )
            info = "Twój system jest aktualny"
            # only if not executed by scheduler
            import homeassistant.components.ais_ai_service as ais_ai

            if say_it or (
                ais_ai.CURR_ENTITIE == "script.ais_update_system"
                and ais_ai.CURR_BUTTON_CODE == 23
            ):
                if ais_global.G_AIS_START_IS_DONE:
                    await hass.services.async_call(
                        "ais_ai_service", "say_it", {"text": info}
                    )
            info += release_notes
            hass.states.async_set(
                "script.ais_update_system",
                "off",
                {
                    ATTR_FRIENDLY_NAME: " Sprawdź dostępność aktualizacji",
                    "icon": "mdi:refresh",
                },
            )
            _LOGGER.info("You are on the latest version of Assystent domowy")

    # Update daily, start at 9AM + some random minutes and seconds based on the system startup
    _dt = dt_util.utcnow()
    event.async_track_utc_time_change(
        hass, check_new_version, hour=9, minute=_dt.minute, second=_dt.second
    )

    def upgrade_package_task(package):
        _LOGGER.info("upgrade_package_task " + str(package))
        env = os.environ.copy()
        args = [sys.executable, "-m", "pip", "install", "--quiet", package, "--upgrade"]
        process = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=env)
        _, stderr = process.communicate()
        if process.returncode != 0:
            _LOGGER.error(
                "Unable to install package %s: %s",
                package,
                stderr.decode("utf-8").lstrip().strip(),
            )
        else:
            if package.startswith("youtube_dl"):
                path = (
                    str(
                        os.path.abspath(
                            os.path.join(
                                os.path.dirname(__file__), "..", "ais_yt_service"
                            )
                        )
                    )
                    + "/manifest.json"
                )
                manifest = {
                    "domain": "ais_yt_service",
                    "name": "AIS YouTube",
                    "config_flow": False,
                    "documentation": "https://ai-speaker.com",
                    "requirements": [package],
                    "dependencies": [],
                    "codeowners": [],
                }
                with open(path, "w+") as jsonFile:
                    json.dump(manifest, jsonFile)

    def upgrade_package(call):
        """ Ask AIS dom service if the package need to be upgraded,
            if yes -> Install a package on PyPi
        """
        if "package" not in call.data:
            _LOGGER.error("No package specified")
            return
        package = call.data["package"]
        if "version" in call.data:
            package = package + "==" + call.data["version"]
        _LOGGER.info("Attempting install of %s", package)
        # todo Starting the installation as independent task
        import threading

        update_thread = threading.Thread(target=upgrade_package_task, args=(package,))
        update_thread.start()

    async def execute_upgrade(call):
        await do_execute_upgrade(hass, call)

    async def download_upgrade(call):
        await do_download_upgrade(hass, call)

    # register services
    hass.services.async_register(DOMAIN, SERVICE_CHECK_VERSION, check_new_version)
    hass.services.async_register(DOMAIN, SERVICE_UPGRADE_PACKAGE, upgrade_package)
    hass.services.async_register(DOMAIN, SERVICE_EXECUTE_UPGRADE, execute_upgrade)
    hass.services.async_register(DOMAIN, SERVICE_DOWNLOAD_UPGRADE, download_upgrade)
    return True


def get_current_dt():
    from datetime import datetime

    now = datetime.now()
    return now.strftime("%d/%m/%Y %H:%M:%S")


def get_current_android_apk_version():
    import subprocess

    try:
        apk_version = subprocess.check_output(
            'su -c "dumpsys package pl.sviete.dom | grep versionName"',
            shell=True,
            timeout=15,
        )
        apk_version = (
            apk_version.decode("utf-8")
            .replace("\n", "")
            .strip()
            .replace("versionName=", "")
        )
        return apk_version
    except Exception as e:
        _LOGGER.info("Can't get android apk version! " + str(e))
        return "0"


def get_current_linux_apt_version():
    pass
    return "0"


async def get_system_info(hass, include_components):
    """Return info about the system."""
    global G_CURRENT_ANDROID_VERSION
    global G_CURRENT_LINUX_VERSION
    gate_id = hass.states.get("sensor.ais_secure_android_id_dom").state
    G_CURRENT_ANDROID_VERSION = get_current_android_apk_version()
    G_CURRENT_LINUX_VERSION = get_current_linux_apt_version()
    info_object = {
        "arch": platform.machine(),
        "os_name": platform.system(),
        "python_version": platform.python_version(),
        "gate_id": gate_id,
        "dom_app_version": current_version,
        "android_app_version": G_CURRENT_ANDROID_VERSION,
        "linux_apt_version": G_CURRENT_LINUX_VERSION,
    }

    if include_components:
        info_object["components"] = list(hass.config.components)

    return info_object


async def get_newest_version(hass, include_components, go_to_download):
    """Get the newest Ais dom version."""
    hass.states.async_set(
        ENTITY_ID,
        "Sprawdzam dostępność aktualizacji",
        {
            ATTR_FRIENDLY_NAME: "Wersja",
            "icon": "mdi:update",
            ATTR_UPDATE_STATUS: UPDATE_STATUS_CHECKING,
            ATTR_UPDATE_CHECK_TIME: get_current_dt(),
        },
    )

    info_object = await get_system_info(hass, include_components)
    session = async_get_clientsession(hass)
    try:
        with async_timeout.timeout(10, loop=hass.loop):
            req = await session.post(UPDATER_URL, json=info_object)
    except (asyncio.TimeoutError, aiohttp.ClientError):
        _LOGGER.error("Could not contact AIS dom to check " "for updates")
        info = "Nie można skontaktować się z usługą AIS dom."
        info += "Spróbuj ponownie później."
        hass.states.async_set(
            ENTITY_ID,
            info,
            {
                ATTR_FRIENDLY_NAME: "Wersja",
                "icon": "mdi:update",
                "dom_app_current_version": current_version,
                "reinstall_dom_app": False,
                "android_app_current_version": G_CURRENT_ANDROID_VERSION,
                "reinstall_android_app": False,
                "linux_apt_current_version": G_CURRENT_LINUX_VERSION,
                "reinstall_linux_apt": False,
                "apt": "",
                "beta": "",
                ATTR_UPDATE_STATUS: UPDATE_STATUS_UPDATED,
                ATTR_UPDATE_CHECK_TIME: get_current_dt(),
            },
        )
        return None

    try:
        res = await req.json()
        # check if we should update
        reinstall_dom_app = False
        reinstall_android_app = False
        reinstall_linux_apt = False
        if StrictVersion(res["dom_app_version"]) > StrictVersion(current_version):
            reinstall_dom_app = True
        if G_CURRENT_ANDROID_VERSION != "0":
            if StrictVersion(res["android_app_version"]) > StrictVersion(
                G_CURRENT_ANDROID_VERSION
            ):
                reinstall_android_app = True
        if G_CURRENT_LINUX_VERSION != "0":
            if StrictVersion(res["linux_apt_version"]) > StrictVersion(
                G_CURRENT_LINUX_VERSION
            ):
                reinstall_linux_apt = True

        need_to_update = False
        info = "Twój system jest aktualny. " + res["release_notes"]
        system_status = UPDATE_STATUS_UPDATED
        if reinstall_dom_app or reinstall_android_app or reinstall_linux_apt:
            need_to_update = True
            info = "Dostępna jest aktualizacja. " + res["release_notes"]
            system_status = UPDATE_STATUS_OUTDATED
        hass.states.async_set(
            ENTITY_ID,
            info,
            {
                ATTR_FRIENDLY_NAME: "Aktualizacja",
                "icon": "mdi:update",
                "dom_app_current_version": current_version,
                "dom_app_newest_version": res["dom_app_version"],
                "reinstall_dom_app": reinstall_dom_app,
                "android_app_current_version": G_CURRENT_ANDROID_VERSION,
                "android_app_newest_version": res["android_app_version"],
                "reinstall_android_app": reinstall_android_app,
                "linux_apt_current_version": G_CURRENT_LINUX_VERSION,
                "linux_apt_newest_version": res["linux_apt_version"],
                "reinstall_linux_apt": reinstall_linux_apt,
                "apt": res["apt"],
                "beta": res["beta"],
                ATTR_UPDATE_STATUS: system_status,
                ATTR_UPDATE_CHECK_TIME: get_current_dt(),
            },
        )
        if need_to_update and go_to_download:
            await hass.services.async_call("ais_updater", "download_upgrade")
        return need_to_update, res["dom_app_version"], res["release_notes"]
    except ValueError:
        _LOGGER.error("Received invalid JSON from AIS dom Update")
        info = "Wersja. Otrzmyano nieprawidłową odpowiedz z usługi AIS dom "
        hass.states.async_set(
            ENTITY_ID,
            info,
            {
                ATTR_FRIENDLY_NAME: "Wersja",
                "icon": "mdi:update",
                "dom_app_current_version": current_version,
                "reinstall_dom_app": False,
                "android_app_current_version": G_CURRENT_ANDROID_VERSION,
                "reinstall_android_app": False,
                "linux_apt_current_version": G_CURRENT_LINUX_VERSION,
                "reinstall_linux_apt": False,
                "apt": "",
                "beta": "",
                ATTR_UPDATE_STATUS: UPDATE_STATUS_UPDATED,
                ATTR_UPDATE_CHECK_TIME: get_current_dt(),
            },
        )
        return None


def get_package_version(package) -> str:
    # import pkg_resources
    # from importlib_metadata import version, PackageNotFoundError
    # req = pkg_resources.Requirement.parse(package)
    #
    # get version from manifest.json
    if package == "youtube_dl":
        path = (
            str(
                os.path.abspath(
                    os.path.join(os.path.dirname(__file__), "..", "ais_yt_service")
                )
            )
            + "/manifest.json"
        )
        with open(path, "r") as f:
            manifest = json.load(f)
        _LOGGER.info(str(manifest["requirements"][0]))
        return manifest["requirements"][0]
    return ""


async def do_execute_upgrade(hass, call):
    say_it = False
    if "say" in call.data:
        say_it = call.data["say"]

    #
    # check the status of the sensor to choice if it's upgrade or version check
    state = hass.states.get("sensor.version_info")
    attr = state.attributes
    reinstall_dom_app = attr.get("reinstall_dom_app", False)
    reinstall_android_app = attr.get("reinstall_android_app", False)
    reinstall_linux_apt = attr.get("reinstall_linux_apt", False)

    if (
        reinstall_dom_app is False
        and reinstall_android_app is False
        and reinstall_linux_apt is False
    ):
        await hass.services.async_call(
            "ais_ai_service", "say_it", {"text": "Sprawdzam dostępność aktualizacji"}
        )
        await hass.services.async_call("ais_updater", "check_version", {"say": say_it})
        return

    # check the newest version before update
    result = await get_newest_version(hass, False, True)
    if result is None:
        return

    need_to_update, dom_app_newest_version, release_notes = result

    if need_to_update:
        pass
        # get_newest_version will call download service


async def do_download_upgrade(hass, call):
    await hass.services.async_call(
        "ais_ai_service", "say_it", {"text": "Pobieram najnowszą wersje systemu."}
    )

    # save the status to sensor and to file
    _set_update_status(hass, UPDATE_STATUS_DOWNLOADING)

    # get the version status from sensor
    state = hass.states.get(ENTITY_ID)
    attr = state.attributes

    #
    reinstall_dom_app = attr.get("reinstall_dom_app", False)
    reinstall_android_app = attr.get("reinstall_android_app", False)
    reinstall_linux_apt = attr.get("reinstall_linux_apt", False)
    apt = attr.get("apt", "")
    beta = attr.get("beta", False)

    # add the grant to save on sdcard

    # download
    import subprocess

    output = subprocess.check_output(
        ["pip", "download", "ais-dom==0.98.9", "-d /sdcard"], universal_newlines=True
    )
    _LOGGER.info("download_upgrade output: " + str(output))
    _set_update_status(hass, UPDATE_STATUS_INSTALLING)

    # add the upgrade call to .bash_profile - to be sure that all will be done
    # call the script

    # when download was started there is no way to stop - we should automatically run next steps
