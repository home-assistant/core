"""
Support to monitoring usb events with inotify on AIS gate.

For more details about this component, please refer to the documentation at
https://www.ai-speaker.com
"""
import asyncio
import fileinput
import json
import logging
import os
import platform
import re
import subprocess

import pyinotify

import homeassistant.components.ais_dom.ais_global as ais_global

DOMAIN = "ais_usb"
_LOGGER = logging.getLogger(__name__)

G_ZIGBEE_DEVICES_ID = ["0451:16a8", "1cf1:0030"]  # CC2531  # Conbee2
G_ZWAVE_ID = "0658:0200"
G_AIS_REMOTE_ID = "0c45:5102"
# ignore internal devices
G_AIS_INTERNAL_DEVICES_ID = ["14cd:8608", "05e3:0608", "1d6b:0002", "1d6b:0003"]

G_USB_DRIVES_PATH = "/mnt/media_rw"
if platform.machine() == "x86_64":
    # local test
    G_USB_DRIVES_PATH = "/media/andrzej"
G_CONBEE_STARTED = False
G_CONBEE_ID = "1cf1:0030"


async def _run(hass, cmd):
    if not ais_global.G_USB_SETTINGS_INFO.get(
        "usbAutoStartServices", True
    ) and cmd.startswith("pm2"):
        pass
    else:
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


def get_device_number(devoce_id):
    # 1. ls -l /dev/ttyACM to find number 166:0
    # 2. use this number in ls -l /sys/dev/char/166:0
    # 3. cat /sys/dev/char/166:0/../../../idProduct
    # find /sys/devices -name 'ttyACM*' -exec cat '{}/../../../idProduct' \;
    # find /sys/devices -name 'ttyACM*' -exec cat {}/../../../idProduct {}/../../../idVendor \;
    tty_acm_paths = (
        subprocess.check_output(
            "find /sys/devices -name 'ttyACM*'", shell=True  # nosec
        )
        .decode("utf-8")
        .strip()
    )
    for line in tty_acm_paths.split("\n"):
        usb_vendor = (
            subprocess.check_output(
                "cat " + line + "/../../../idVendor", shell=True  # nosec
            )
            .decode("utf-8")
            .strip()
        )
        usb_product = (
            subprocess.check_output(
                "cat " + line + "/../../../idProduct", shell=True  # nosec
            )
            .decode("utf-8")
            .strip()
        )
        if usb_vendor + ":" + usb_product == devoce_id:
            return line.split("/")[-1]
    return None


async def say_it(hass, text):
    if not ais_global.G_USB_SETTINGS_INFO.get("usbVoiceNotification", True):
        pass
    else:
        await hass.services.async_call("ais_ai_service", "say_it", {"text": text})


async def prepare_usb_device(hass, device_info):
    global G_CONBEE_STARTED
    # ZIGBEE
    if device_info["id"] in G_ZIGBEE_DEVICES_ID:
        # do not restart conbee
        if G_CONBEE_STARTED and device_info["id"] == G_CONBEE_ID:
            pass
        else:
            # check if zigbee already exists
            # add info in app
            if not os.path.isdir("/data/data/pl.sviete.dom/files/home/zigbee2mqtt"):
                await say_it(
                    hass,
                    "Nie znaleziono pakietu Zigbee2Mqtt zainstaluj go przed pierwszym uruchomieniem usługi "
                    "Zigbee. Szczegóły w dokumentacji Asystenta domowego.",
                )
                return
            # fix permissions
            uid = str(os.getuid())
            gid = str(os.getgid())
            if ais_global.has_root():
                await _run(hass, "su -c 'chown " + uid + ":" + gid + " /dev/ttyACM*'")
            if ais_global.has_root():
                await _run(hass, "su -c 'chmod 777 /dev/ttyACM*'")

            # set the adapter
            adapter = "null"
            if device_info["id"] == "0451:16a8":
                adapter = "zstack"
            if device_info["id"] == G_CONBEE_ID:
                adapter = "deconz"
            # change zigbee settings
            stage_no = 0
            with fileinput.FileInput(
                "/data/data/pl.sviete.dom/files/home/zigbee2mqtt/data/configuration.yaml",
                inplace=True,
                backup=".bak",
            ) as file:
                for line in file:
                    if line.startswith("serial:"):
                        stage_no = 1
                    if 0 < stage_no < 3:
                        if line.startswith("  adapter:"):
                            print("  adapter: " + adapter, end="\n")
                            stage_no = stage_no + 1
                        elif line.startswith("  port:"):
                            device_num = get_device_number(device_info["id"])
                            print("  port: /dev/" + device_num, end="\n")
                            stage_no = stage_no + 1
                        elif line.startswith("  ") or line.startswith("serial:"):
                            print(line, end="")
                        else:
                            # configuration not correct... exit
                            print(line, end="")
                            stage_no = 3
                    else:
                        print(line, end="")

            if ais_global.G_USB_SETTINGS_INFO.get("usbAutoStartServices", True):
                # start zigbee2mqtt service
                # restart-delay 120000 millisecond == 2 minutes
                if device_info["id"] == G_CONBEE_ID:
                    G_CONBEE_STARTED = True
                cmd_to_run = (
                    "pm2 restart zigbee || cd /data/data/pl.sviete.dom/files/home/zigbee2mqtt; pm2 start index.js "
                    "--name zigbee --output /dev/null --error /dev/null --restart-delay=120000"
                )
                await _run(hass, cmd_to_run)
                await say_it(hass, "Uruchomiono serwis zigbee")

    # ZWAVE
    if device_info["id"] == G_ZWAVE_ID:
        # fix permissions
        uid = str(os.getuid())
        gid = str(os.getgid())
        if ais_global.has_root():
            await _run(hass, "su -c 'chown " + uid + ":" + gid + " /dev/ttyACM*'")
            await _run(hass, "su -c 'chmod 777 /dev/ttyACM*'")
        # zwavejs2mqtt exists?
        if not os.path.isdir("/data/data/pl.sviete.dom/files/home/zwavejs2mqtt"):
            await say_it(
                hass,
                "Nie znaleziono pakietu ZwaveJs2Mqtt zainstaluj go przed pierwszym uruchomieniem usługi "
                "Zwave. Szczegóły w dokumentacji Asystenta domowego.",
            )
            return
        else:
            device_num = get_device_number(device_info["id"])
            try:
                with open(
                    "/data/data/pl.sviete.dom/files/home/zwavejs2mqtt/store/settings.json"
                ) as file_r:
                    zwave_settings_json = json.load(file_r)

                zwave_settings_json["zwave"]["port"] = "/dev/" + device_num

                with open(
                    "/data/data/pl.sviete.dom/files/home/zwavejs2mqtt/store/settings.json",
                    "w",
                ) as file_w:
                    json.dump(zwave_settings_json, file_w)
            except Exception as e:
                _LOGGER.error("Zwave settings error, exception: " + str(e))
                await say_it(hass, "Sprawdź ustawienia Zwave w aplikacji.")

            if ais_global.G_USB_SETTINGS_INFO.get("usbAutoStartServices", True):
                cmd_to_run = (
                    "pm2 restart zwave || pm2 start /data/data/pl.sviete.dom/files/home/zwavejs2mqtt/server/bin/www.js "
                    "--name zwave --output /dev/null --error /dev/null --restart-delay=120000"
                )
                await _run(hass, cmd_to_run)
                #
                await say_it(hass, "Uruchomiono serwis zwave")


async def remove_usb_device(hass, device_info):
    # stop service and remove device from dict
    if device_info in ais_global.G_USB_DEVICES:
        ais_global.G_USB_DEVICES.remove(device_info)

    if ais_global.G_USB_SETTINGS_INFO.get("usbAutoStartServices", True):
        # do not restart conbee
        if device_info["id"] != G_CONBEE_ID:
            if device_info["id"] in G_ZIGBEE_DEVICES_ID:
                await _run(hass, "pm2 delete zigbee")
                await say_it(hass, "Zatrzymano serwis zigbee")
            elif device_info["id"] == G_ZWAVE_ID:
                await _run(hass, "pm2 delete zwave")
                await say_it(hass, "Zatrzymano serwis zwave")


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
                        say_it(hass, "Dodano wymienny dysk_" + str(drive_id))
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
                            if not G_CONBEE_STARTED or device_info["id"] != G_CONBEE_ID:
                                text = "Dodano: " + device_info["info"]
                                hass.async_add_job(say_it(hass, text))
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
                        hass.async_add_job(say_it(hass, "Usunięto wymienny " + str(f)))
                        # fill the list
                        hass.async_add_job(
                            hass.services.async_call("ais_usb", "ls_flash_drives")
                        )
            else:
                device_info = get_device_info(event.pathname)
                if device_info is not None:
                    if (
                        device_info["id"]
                        not in (G_AIS_REMOTE_ID, G_ZWAVE_ID, G_ZIGBEE_DEVICES_ID)
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
                                        if ais_global.G_LOG_SETTINGS_INFO[
                                            "logDrive"
                                        ] != "-" and not os.path.isfile(
                                            ais_global.G_REMOTE_DRIVES_DOM_PATH
                                            + "/"
                                            + ais_global.G_LOG_SETTINGS_INFO["logDrive"]
                                            + "/ais.log"
                                        ):
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
                            # do not restart conbee
                            and device_info["id"] != G_CONBEE_ID
                        ):
                            text = "Usunięto: " + device_info["info"]
                            hass.async_add_job(say_it(hass, text))
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
        if ais_global.G_USB_SETTINGS_INFO.get("usbAutoStartServices", True):
            ais_global.G_USB_DEVICES = _lsusb()
            zigbee_adapter = False
            zwave_adapter = False
            for device in ais_global.G_USB_DEVICES:
                if device["id"] in G_ZIGBEE_DEVICES_ID:
                    zigbee_adapter = True
                if device["id"] in G_ZWAVE_ID:
                    zwave_adapter = True
            # remove zigbee service on start if adapter not exist
            if not zigbee_adapter:
                await _run(hass, "pm2 delete zigbee")
            #
            if not zwave_adapter:
                await _run(hass, "pm2 delete zwave")

    async def lsusb(call):
        # check if the call was from scheduler or service / web app
        ais_global.G_USB_DEVICES = _lsusb()
        for device in ais_global.G_USB_DEVICES:
            # check if USB is zigbee or zwave dongle
            await prepare_usb_device(hass, device)

    async def mount_external_drives(call):
        """mount_external_drives."""
        try:
            await _run(hass, "rm " + ais_global.G_REMOTE_DRIVES_DOM_PATH + "/*")
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
        if not os.path.exists(ais_global.G_REMOTE_DRIVES_DOM_PATH):
            os.makedirs(ais_global.G_REMOTE_DRIVES_DOM_PATH)
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

    async def check_ais_usb_settings(call):
        # get USB settings from file
        file_path = hass.config.config_dir + ais_global.G_USB_SETTINGS_INFO_FILE
        try:
            with open(file_path) as usb_settings_file:
                ais_global.G_USB_SETTINGS_INFO = json.loads(usb_settings_file.read())
        except Exception:
            with open(
                hass.config.config_dir + ais_global.G_USB_SETTINGS_INFO_FILE, "w"
            ) as outfile:
                json.dump(
                    {"usbAutoStartServices": True, "usbVoiceNotification": True},
                    outfile,
                )
            ais_global.G_USB_SETTINGS_INFO = {
                "usbAutoStartServices": True,
                "usbVoiceNotification": True,
            }

    hass.services.async_register(DOMAIN, "stop_devices", stop_devices)
    hass.services.async_register(DOMAIN, "lsusb", lsusb)
    hass.services.async_register(DOMAIN, "mount_external_drives", mount_external_drives)
    hass.services.async_register(DOMAIN, "ls_flash_drives", ls_flash_drives)
    hass.services.async_register(
        DOMAIN, "check_ais_usb_settings", check_ais_usb_settings
    )

    hass.async_add_job(usb_load_notifiers)

    return True


def _lsusb():
    device_re = re.compile(
        r"Bus\s+(?P<bus>\d+)\s+Device\s+(?P<device>\d+).+ID\s(?P<id>\w+:\w+)", re.I
    )
    if ais_global.has_root():
        df = subprocess.check_output("su -c lsusb", shell=True)  # nosec
    else:
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
                        G_ZIGBEE_DEVICES_ID,
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
                            if device["id"] in G_ZIGBEE_DEVICES_ID:
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
