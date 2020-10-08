"""
Support to monitoring usb events with inotify on AIS gate.

For more details about this component, please refer to the documentation at
https://www.ai-speaker.com
"""
import asyncio
import logging
import os
import platform
import re
import subprocess

import pyinotify

import homeassistant.components.ais_dom.ais_global as ais_global

DOMAIN = "ais_usb"
_LOGGER = logging.getLogger(__name__)

G_ZIGBEE_ID = "0451:16a8"
G_ZWAVE_ID = "0658:0200"
G_AIS_REMOTE_ID = "0c45:5102"
# ignore internal devices
G_AIS_INTERNAL_DEVICES_ID = ["14cd:8608", "05e3:0608", "1d6b:0002", "1d6b:0003"]

G_USB_DRIVES_PATH = "/mnt/media_rw"
if platform.machine() == "x86_64":
    # local test
    G_USB_DRIVES_PATH = "/media/andrzej"


async def _run(cmd):
    cmd_process = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await cmd_process.communicate()

    if stdout:
        _LOGGER.info(f"[stdout]\n{stdout.decode()}")
    if stderr:
        _LOGGER.info(f"[stderr]\n{stderr.decode()}")


# check if usb is valid external drive
def is_usb_url_valid_external_drive(path):
    # check if the path is correct for external usb / sdcard usr
    path = path.replace("sqlite:////", "")
    path = path.replace("/ais.db", "")
    path = path.replace("/ais.log", "")
    if os.path.islink(path):
        if os.readlink(path).startswith(G_USB_DRIVES_PATH):
            return True
    return False


def get_device_info(pathname):
    # get devices full info via pathname
    bus = pathname.split("/")[-2]
    device = pathname.split("/")[-1]
    # find the id of the connected device
    for d in ais_global.G_USB_DEVICES:
        if d["bus"] == bus and d["device"] == device:
            return d

    return None


async def prepare_usb_device(hass, device_info):
    # start zigbee2mqtt service
    # add info in app
    if device_info["id"] == G_ZIGBEE_ID:
        # Register the built-in zigbee panel
        # hass.components.frontend.async_register_built_in_panel(
        #     "aiszigbee",
        #     require_admin=True,
        #     sidebar_title="Zigbee",
        #     sidebar_icon="mdi:zigbee",
        #     update=True,
        # )

        # check if zigbee already exists
        if not os.path.isdir("/data/data/pl.sviete.dom/files/home/zigbee2mqtt"):
            await hass.services.async_call(
                "ais_ai_service",
                "say_it",
                {
                    "text": "Nie znaleziono pakietu Zigbee2Mqtt zainstaluj go przed pierwszym uruchomieniem usługi "
                    "Zigbee. Szczegóły w dokumentacji Asystenta domowego."
                },
            )
            return

        # fix permitions
        uid = str(os.getuid())
        gid = str(os.getgid())
        if ais_global.has_root():
            await _run("su -c 'chown " + uid + ":" + gid + " /dev/ttyACM0'")
        # TODO check the /dev/ttyACM.. number
        if ais_global.has_root():
            await _run("su -c 'chmod 777 /dev/ttyACM0'")

        # restart-delay 120000 milisecond == 2 minutes
        cmd_to_run = (
            "pm2 restart zigbee || pm2 start /data/data/pl.sviete.dom/files/home/zigbee2mqtt/index.js "
            "--name zigbee --output /dev/null --error /dev/null --restart-delay=120000"
        )
        await _run(cmd_to_run)

        #
        # if ais_global.G_AIS_START_IS_DONE:
        await hass.services.async_call(
            "ais_ai_service", "say_it", {"text": "Uruchomiono serwis zigbee"}
        )


async def remove_usb_device(hass, device_info):
    # stop service and remove device from dict
    ais_global.G_USB_DEVICES.remove(device_info)

    if device_info["id"] == G_ZIGBEE_ID:
        # Unregister the built-in zigbee panel
        # hass.components.frontend.async_remove_panel("aiszigbee")
        # stop pm2 zigbee service
        await _run("pm2 delete zigbee")
        await hass.services.async_call(
            "ais_ai_service", "say_it", {"text": "Zatrzymano serwis zigbee"}
        )


async def async_setup(hass, config):
    """Set up the usb events component."""

    class EventHandler(pyinotify.ProcessEvent):
        def process_IN_CREATE(self, event):
            if event.pathname.startswith(G_USB_DRIVES_PATH):
                # create symlink
                try:
                    drive_id = event.pathname.replace(
                        G_USB_DRIVES_PATH + "/", ""
                    ).strip()

                    os.symlink(
                        str(event.pathname),
                        ais_global.G_REMOTE_DRIVES_DOM_PATH + "/dysk_" + str(drive_id),
                    )
                    hass.async_add_job(
                        hass.services.async_call(
                            "ais_ai_service",
                            "say_it",
                            {"text": "Dodano wymienny dysk_" + str(drive_id)},
                        )
                    )
                    # fill the list
                    hass.async_add_job(
                        hass.services.async_call("ais_usb", "ls_flash_drives")
                    )
                except Exception as e:
                    _LOGGER.error("mount_external_drives" + str(e))

            else:
                ais_global.G_USB_DEVICES = _lsusb()
                device_info = get_device_info(event.pathname)
                if device_info is not None:
                    if (
                        device_info["id"] != G_AIS_REMOTE_ID
                        or ais_global.G_USB_INTERNAL_MIC_RESET is False
                    ):
                        if (
                            "info" in device_info
                            and "xHCI Host Controller" not in device_info["info"]
                            and "Mass Storage" not in device_info["info"]
                        ):
                            text = "Dodano: " + device_info["info"]
                            hass.async_add_job(
                                hass.services.async_call(
                                    "ais_ai_service", "say_it", {"text": text}
                                )
                            )
                    # reset flag
                    ais_global.G_USB_INTERNAL_MIC_RESET = False
                    # prepare device
                    hass.async_add_job(prepare_usb_device(hass, device_info))

        def process_IN_DELETE(self, event):
            if event.pathname.startswith(G_USB_DRIVES_PATH):
                # delete symlink
                for f in os.listdir(ais_global.G_REMOTE_DRIVES_DOM_PATH):
                    if str(
                        os.path.realpath(
                            os.path.join(ais_global.G_REMOTE_DRIVES_DOM_PATH, f)
                        )
                    ) == str(event.pathname):
                        os.system(
                            "rm " + ais_global.G_REMOTE_DRIVES_DOM_PATH + "/" + str(f)
                        )
                        hass.async_add_job(
                            hass.services.async_call(
                                "ais_ai_service",
                                "say_it",
                                {"text": "Usunięto wymienny " + str(f)},
                            )
                        )
                        # fill the list
                        hass.async_add_job(
                            hass.services.async_call("ais_usb", "ls_flash_drives")
                        )
            else:
                device_info = get_device_info(event.pathname)
                if device_info is not None:
                    if (
                        device_info["id"] not in (G_AIS_REMOTE_ID, G_ZIGBEE_ID)
                        and ais_global.G_USB_INTERNAL_MIC_RESET is False
                    ):
                        if "info" in device_info:
                            if (
                                "info" in device_info
                                and "xHCI Host Controller " not in device_info["info"]
                            ):
                                # quick stop access to files - to prevent
                                # ProcessKiller: Process xxx (10754) has open file /mnt/media_rw/...
                                # ProcessKiller: Sending Interrupt to process 10754

                                # 1. check the if log file exists, if not then stop logs
                                if ais_global.G_LOG_SETTINGS_INFO is not None:
                                    if "logDrive" in ais_global.G_LOG_SETTINGS_INFO:
                                        if not os.path.isfile(
                                            ais_global.G_REMOTE_DRIVES_DOM_PATH
                                            + "/"
                                            + ais_global.G_LOG_SETTINGS_INFO["logDrive"]
                                            + "/ais.log"
                                        ):
                                            print("usb ais_stop_logs_event")
                                            hass.bus.async_fire("ais_stop_logs_event")
                                # 2. check the if recorder db file exists, if not then stop recorder
                                if ais_global.G_DB_SETTINGS_INFO is not None:
                                    if (
                                        "dbUrl" in ais_global.G_DB_SETTINGS_INFO
                                        and ais_global.G_REMOTE_DRIVES_DOM_PATH
                                        in ais_global.G_DB_SETTINGS_INFO["dbUrl"]
                                    ):
                                        if not os.path.isfile(
                                            ais_global.G_DB_SETTINGS_INFO[
                                                "dbUrl"
                                            ].replace("sqlite:////", "")
                                        ):
                                            print("usb ais_stop_recorder_event")
                                            hass.bus.async_fire(
                                                "ais_stop_recorder_event"
                                            )

                                # 3. check the if media file exists, if not then stop player
                                state = hass.states.get(
                                    "media_player.wbudowany_glosnik"
                                )
                                attr = state.attributes
                                media_content_id = attr.get("media_content_id")
                                if (
                                    media_content_id is not None
                                    and ais_global.G_REMOTE_DRIVES_DOM_PATH
                                    in media_content_id
                                ):
                                    if not os.path.isfile(media_content_id):
                                        # quick stop player - to prevent
                                        # ProcessKiller: Process pl.sviete.dom (10754) has open file /mnt/media_rw/...
                                        # ProcessKiller: Sending Interrupt to process 10754
                                        hass.services.call(
                                            "ais_ai_service",
                                            "publish_command_to_frame",
                                            {"key": "stopAudio", "val": True},
                                        )

                    # info to user
                    if (
                        device_info["id"] != G_AIS_REMOTE_ID
                        or ais_global.G_USB_INTERNAL_MIC_RESET is False
                    ):
                        if (
                            "info" in device_info
                            and "xHCI Host Controller" not in device_info["info"]
                            and "Mass Storage" not in device_info["info"]
                        ):
                            text = "Usunięto: " + device_info["info"]
                            hass.async_add_job(
                                hass.services.async_call(
                                    "ais_ai_service", "say_it", {"text": text}
                                )
                            )
                    # remove device
                    hass.async_add_job(remove_usb_device(hass, device_info))

    # USB
    async def usb_load_notifiers():
        _LOGGER.info("usb_load_notifiers start")
        wm = pyinotify.WatchManager()  # Watch Manager
        mask = pyinotify.IN_DELETE | pyinotify.IN_CREATE  # watched events
        notifier = pyinotify.ThreadedNotifier(wm, EventHandler())
        notifier.start()
        wm.add_watch("/dev/bus", mask, rec=True)
        wm.add_watch(G_USB_DRIVES_PATH, mask, rec=False)
        _LOGGER.info("usb_load_notifiers stop")

    async def stop_devices(call):
        # remove zigbee service on start - to prevent pm2 for restarting when usb is not connected
        await _run("pm2 delete zigbee")
        #

    async def lsusb(call):
        # check if the call was from scheduler or service / web app
        ais_global.G_USB_DEVICES = _lsusb()
        for device in ais_global.G_USB_DEVICES:
            if device["id"] == G_ZIGBEE_ID:
                # USB zigbee dongle
                await prepare_usb_device(hass, device)

    async def mount_external_drives(call):
        """mount_external_drives."""
        try:
            await _run("rm " + ais_global.G_REMOTE_DRIVES_DOM_PATH + "/*")
            dirs = os.listdir(G_USB_DRIVES_PATH)
            for d in dirs:
                os.symlink(
                    G_USB_DRIVES_PATH + "/" + d,
                    ais_global.G_REMOTE_DRIVES_DOM_PATH + "/dysk_" + d,
                )
        except Exception as e:
            _LOGGER.error("mount_external_drives " + str(e))

    async def ls_flash_drives(call):
        ais_usb_flash_drives = [ais_global.G_EMPTY_OPTION]
        dirs = os.listdir(ais_global.G_REMOTE_DRIVES_DOM_PATH)
        for d in dirs:
            ais_usb_flash_drives.append(d)
        # set drives on list
        await hass.services.async_call(
            "input_select",
            "set_options",
            {
                "entity_id": "input_select.ais_usb_flash_drives",
                "options": ais_usb_flash_drives,
            },
        )

    hass.services.async_register(DOMAIN, "stop_devices", stop_devices)
    hass.services.async_register(DOMAIN, "lsusb", lsusb)
    hass.services.async_register(DOMAIN, "mount_external_drives", mount_external_drives)
    hass.services.async_register(DOMAIN, "ls_flash_drives", ls_flash_drives)

    hass.async_add_job(usb_load_notifiers)
    return True


def _lsusb():
    device_re = re.compile(
        r"Bus\s+(?P<bus>\d+)\s+Device\s+(?P<device>\d+).+ID\s(?P<id>\w+:\w+)", re.I
    )
    df = subprocess.check_output("lsusb")
    devices = []
    for i in df.decode("utf-8").split("\n"):
        if i:
            info = device_re.match(i)
            if info:
                dinfo = info.groupdict()
                if dinfo["id"] not in G_AIS_INTERNAL_DEVICES_ID:
                    devices.append(dinfo)

    di = subprocess.check_output("ls /sys/bus/usb/devices", shell=True)  # nosec
    for d in di.decode("utf-8").split("\n"):
        manufacturer = ""
        product = ""
        # if idVendor file exist we can try to get the info about device
        if os.path.exists("/sys/bus/usb/devices/" + d + "/idVendor"):
            try:
                id_vendor = (
                    subprocess.check_output(
                        "cat /sys/bus/usb/devices/" + d + "/idVendor",
                        shell=True,  # nosec
                    )
                    .decode("utf-8")
                    .strip()
                )
                id_product = (
                    subprocess.check_output(
                        "cat /sys/bus/usb/devices/" + d + "/idProduct",
                        shell=True,  # nosec
                    )
                    .decode("utf-8")
                    .strip()
                )
                id_vendor_product = id_vendor + ":" + id_product
                manufacturer = " "
                product = ""
                if id_vendor_product not in G_AIS_INTERNAL_DEVICES_ID:
                    if id_vendor_product not in [
                        G_ZIGBEE_ID,
                        G_ZWAVE_ID,
                        G_AIS_REMOTE_ID,
                    ]:
                        product = (
                            subprocess.check_output(
                                "cat /sys/bus/usb/devices/" + d + "/product",
                                shell=True,  # nosec
                            )
                            .decode("utf-8")
                            .strip()
                        )
                        if os.path.exists(
                            "/sys/bus/usb/devices/" + d + "/manufacturer"
                        ):
                            manufacturer = (
                                subprocess.check_output(
                                    "cat /sys/bus/usb/devices/" + d + "/manufacturer",
                                    shell=True,  # nosec
                                )
                                .decode("utf-8")
                                .strip()
                            )
                            if manufacturer != product:
                                # do not say Android producent Android
                                manufacturer = " producent " + manufacturer
                            else:
                                manufacturer = " "
                        else:
                            manufacturer = " "

                        _LOGGER.debug(
                            "id_vendor: "
                            + id_vendor
                            + " id_product: "
                            + id_product
                            + " product: "
                            + product
                            + " manufacturer: "
                            + manufacturer
                        )
                    #
                    for device in devices:
                        if device["id"] == id_vendor_product:
                            device["product"] = product
                            device["manufacturer"] = manufacturer
                            # special cases
                            if device["id"] == G_ZIGBEE_ID:
                                # USB zigbee dongle
                                device["info"] = (
                                    "urządzenie Zigbee" + product + manufacturer
                                )
                            elif device["id"] == G_AIS_REMOTE_ID:
                                # USB ais remote dongle
                                device[
                                    "info"
                                ] = "urządzenie Pilot radiowy z mikrofonem, producent AI-Speaker"
                            elif device["id"] == G_ZWAVE_ID:
                                # USB ais zwave dongle
                                device["info"] = "urządzenie Z-Wave Aeotec"
                            else:
                                device["info"] = (
                                    "urządzenie " + str(product) + str(manufacturer)
                                )

            except Exception as e:
                _LOGGER.debug("no info about usb in: /sys/bus/usb/devices/" + d)

    return devices
