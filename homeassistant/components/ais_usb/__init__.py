"""
Support to monitoring usb events with inotify on AIS gate.

For more details about this component, please refer to the documentation at
https://www.ai-speaker.com
"""
import asyncio
import logging
import pyinotify
import asyncore

DOMAIN = "ais_usb"
_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
async def async_setup(hass, config):
    """Set up the usb events component."""
    #
    wm = pyinotify.WatchManager()  # Watch Manager
    mask = pyinotify.IN_DELETE | pyinotify.IN_CREATE  # watched events

    class EventHandler(pyinotify.ProcessEvent):
        def process_IN_CREATE(self, event):
            # TODO check the device via lsusb
            print("Creating:", event.pathname)
            hass.async_add_job(
                hass.services.async_call(
                    "ais_ai_service", "say_it", {"text": "Dodano: " + event.pathname}
                )
            )

        def process_IN_DELETE(self, event):
            print("Removing:", event.pathname)
            # TODO check the device via lsusb
            hass.async_add_job(
                hass.services.async_call(
                    "ais_ai_service", "say_it", {"text": "Usunmięto: " + event.pathname}
                )
            )

    notifier = pyinotify.ThreadedNotifier(wm, EventHandler())
    notifier.start()
    excl_lst = ["^/dev/shm"]
    excl = pyinotify.ExcludeFilter(excl_lst)
    wdd = wm.add_watch("/dev", mask, rec=True, exclude_filter=excl)

    async def lsusb(call):
        # check if the call was from scheduler or service / web app
        _lsusb(hass, call)

    hass.services.async_register(DOMAIN, "lsusb", lsusb)
    return True


def _lsusb(hass, call):
    _LOGGER.info("OK")
    pass
