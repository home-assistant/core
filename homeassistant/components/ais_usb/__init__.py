"""
Support to monitoring usb events with inotify on AIS gate.

For more details about this component, please refer to the documentation at
https://www.ai-speaker.com
"""
import asyncio
import logging
import os
import re
import subprocess
import platform

import pyinotify

import homeassistant.components.ais_dom.ais_global as ais_global

DOMAIN = "ais_usb"
_LOGGER = logging.getLogger(__name__)
G_ZIGBEE_ID = "0451:16a8"
G_AIS_REMOTE_ID = "0c45:5102"

G_USB_DRIVES_PATH = "/mnt/media_rw"
if platform.machine() == "x86_64":
    # local test
    G_USB_DRIVES_PATH = "/media/andrzej"


def get_device_info(pathname):
    # get devices full info via pathname
    bus = pathname.split("/")[-2]
    device = pathname.split("/")[-1]
    # find the id of the connected device
    for d in ais_global.G_USB_DEVICES:
        if d["bus"] == bus and d["device"] == device:
            return d

    return None


def prepare_usb_device(hass, device_info):
    # start zigbee2mqtt service

    # add info in app
    if device_info["id"] == G_ZIGBEE_ID:
        # Register the built-in zigbee panel
        hass.components.frontend.async_register_built_in_panel(
            "lovelace/ais_zigbee",
            require_admin=True,
            sidebar_title="Zigbee",
            sidebar_icon="mdi:zigbee",
        )

        # check if zigbee already exists
        if not os.path.isdir("/data/data/pl.sviete.dom/files/home/zigbee2mqtt"):
            # download
            hass.async_add_job(
                hass.services.async_call(
                    "ais_ai_service",
                    "say_it",
                    {
                        "text": "Nie znaleziono pakietu Zigbee2Mqtt zainstaluj go przed pierwszym uruchomieniem usługi "
                        "Zigbee. Szczegóły w dokumentacji Asystenta domowego."
                    },
                )
            )
            return

        # start pm2 zigbee service
        os.system("pm2 stop zigbee")
        os.system("pm2 delete zigbee")
        os.system(
            "cd /data/data/pl.sviete.dom/files/home/zigbee2mqtt && pm2 start npm --name zigbee --output NULL "
            "--error NULL --restart-delay=30000 -- run start "
        )
        os.system("pm2 save")
        if ais_global.G_AIS_START_IS_DONE:
            hass.async_add_job(
                hass.services.async_call(
                    "ais_ai_service", "say_it", {"text": "Uruchomiono serwis zigbee"}
                )
            )


def remove_usb_device(hass, device_info):
    # stop service and remove device from dict
    ais_global.G_USB_DEVICES.remove(device_info)

    if device_info["id"] == G_ZIGBEE_ID:
        # Unregister the built-in zigbee panel
        hass.components.frontend.async_remove_panel("lovelace/ais_zigbee")
        # stop pm2 zigbee service
        os.system("pm2 stop zigbee")
        os.system("pm2 delete zigbee")
        os.system("pm2 save")
        hass.async_add_job(
            hass.services.async_call(
                "ais_ai_service", "say_it", {"text": "Zatrzymano serwis zigbee"}
            )
        )


@asyncio.coroutine
async def async_setup(hass, config):
    """Set up the usb events component."""
    wm = pyinotify.WatchManager()  # Watch Manager
    mask = pyinotify.IN_DELETE | pyinotify.IN_CREATE  # watched events

    class EventHandler(pyinotify.ProcessEvent):
        def process_IN_CREATE(self, event):
            if event.pathname.startswith(G_USB_DRIVES_PATH):
                # create symlink
                lno = len(
                    os.listdir(
                        "/data/data/pl.sviete.dom/files/home/dom/dyski-wymienne/"
                    )
                )
                try:
                    os.symlink(
                        str(event.pathname),
                        "/data/data/pl.sviete.dom/files/home/dom/dyski-wymienne/dysk_"
                        + str(lno + 1),
                    )
                    hass.async_add_job(
                        hass.services.async_call(
                            "ais_ai_service",
                            "say_it",
                            {"text": "Dodano wymienny dysk_" + str(lno + 1)},
                        )
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
                        if "info" in device_info:
                            text = "Dodano: " + device_info["info"]
                        else:
                            text = "Dodano urządzenie"
                        hass.async_add_job(
                            hass.services.async_call(
                                "ais_ai_service", "say_it", {"text": text}
                            )
                        )
                    # reset flag
                    ais_global.G_USB_INTERNAL_MIC_RESET = False
                    # prepare device
                    prepare_usb_device(hass, device_info)

        def process_IN_DELETE(self, event):
            if event.pathname.startswith(G_USB_DRIVES_PATH):
                # delete symlink
                td = "/data/data/pl.sviete.dom/files/home/dom/dyski-wymienne"
                for f in os.listdir(td):
                    if str(os.path.realpath(os.path.join(td, f))) == str(
                        event.pathname
                    ):
                        os.system("rm " + td + "/" + str(f))
                        hass.async_add_job(
                            hass.services.async_call(
                                "ais_ai_service",
                                "say_it",
                                {"text": "Usunięto wymienny " + str(f)},
                            )
                        )

            else:
                device_info = get_device_info(event.pathname)
                if device_info is not None:
                    if (
                        device_info["id"] != G_AIS_REMOTE_ID
                        or ais_global.G_USB_INTERNAL_MIC_RESET is False
                    ):
                        if "info" in device_info:
                            text = "Usunięto: " + device_info["info"]
                        else:
                            text = "Usunięto urządzenie"
                        hass.async_add_job(
                            hass.services.async_call(
                                "ais_ai_service", "say_it", {"text": text}
                            )
                        )
                    # remove device
                    remove_usb_device(hass, device_info)

    # USB
    notifier = pyinotify.ThreadedNotifier(wm, EventHandler())
    notifier.start()
    wm.add_watch("/dev/bus", mask, rec=True)
    wm.add_watch(G_USB_DRIVES_PATH, mask, rec=True)

    async def stop_devices(call):
        # remove zigbee service on start - to prevent pm2 for restarting when usb is not connected
        os.system("pm2 stop zigbee")
        os.system("pm2 delete zigbee")
        os.system("pm2 save")
        #

    async def lsusb(call):
        # check if the call was from scheduler or service / web app
        devices = _lsusb()
        for device in devices:
            if device["id"] == G_ZIGBEE_ID:
                # USB zigbee dongle
                prepare_usb_device(hass, device)

    async def mount_external_drives(call):
        try:
            os.system("rm /data/data/pl.sviete.dom/files/home/dom/dyski-wymienne/*")
            dirs = os.listdir(G_USB_DRIVES_PATH)
            for i in range(0, len(dirs)):
                os.symlink(
                    G_USB_DRIVES_PATH + "/" + dirs[i],
                    "/data/data/pl.sviete.dom/files/home/dom/dyski-wymienne/dysk_"
                    + str(i + 1),
                )
        except Exception as e:
            _LOGGER.error("mount_external_drives" + str(e))

    hass.services.async_register(DOMAIN, "stop_devices", stop_devices)
    hass.services.async_register(DOMAIN, "lsusb", lsusb)
    hass.services.async_register(DOMAIN, "mount_external_drives", mount_external_drives)
    return True


def _lsusb():
    device_re = re.compile(
        "Bus\s+(?P<bus>\d+)\s+Device\s+(?P<device>\d+).+ID\s(?P<id>\w+:\w+)", re.I
    )
    df = subprocess.check_output("lsusb")
    devices = []
    for i in df.decode("utf-8").split("\n"):
        if i:
            info = device_re.match(i)
            if info:
                dinfo = info.groupdict()
                devices.append(dinfo)

    di = subprocess.check_output("ls /sys/bus/usb/devices", shell=True)
    for d in di.decode("utf-8").split("\n"):
        manufacturer = ""
        product = ""
        try:
            id_vendor = (
                subprocess.check_output(
                    "cat /sys/bus/usb/devices/" + d + "/idVendor", shell=True
                )
                .decode("utf-8")
                .strip()
            )
            id_product = (
                subprocess.check_output(
                    "cat /sys/bus/usb/devices/" + d + "/idProduct", shell=True
                )
                .decode("utf-8")
                .strip()
            )
            product = (
                subprocess.check_output(
                    "cat /sys/bus/usb/devices/" + d + "/product", shell=True
                )
                .decode("utf-8")
                .strip()
            )
            try:
                manufacturer = (
                    subprocess.check_output(
                        "cat /sys/bus/usb/devices/" + d + "/manufacturer", shell=True
                    )
                    .decode("utf-8")
                    .strip()
                )
                manufacturer = " producent " + manufacturer
            except Exception as e:
                manufacturer = " "

            _LOGGER.info("id_vendor: " + id_vendor)
            _LOGGER.info("id_product: " + id_product)
            _LOGGER.info("product: " + product)
            _LOGGER.info("manufacturer: " + manufacturer)
            for device in devices:
                if device["id"] == id_vendor + ":" + id_product:
                    device["product"] = product
                    device["manufacturer"] = manufacturer
                    # special cases
                    if device["id"] == G_ZIGBEE_ID:
                        # USB zigbee dongle
                        device["info"] = "urządzenie Zigbee" + product + manufacturer
                    elif device["id"] == G_AIS_REMOTE_ID:
                        # USB ais remote dongle
                        device[
                            "info"
                        ] = "urządzenie Pilot radiowy z mikrofonem, producent AI-Speaker"
                    else:
                        device["info"] = (
                            "urządzenie " + str(product) + str(manufacturer)
                        )

        except Exception as e:
            _LOGGER.info("no info about usb in: /sys/bus/usb/devices/" + d)

    return devices
