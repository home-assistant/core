"""
Exposes Amplifier Srvice on AIS dom device

For more details about this platform, please refer to the documentation at
https://ai-speaker.com
"""
import asyncio
import os
import logging
DOMAIN = 'ais_amplifier_service'
_LOGGER = logging.getLogger(__name__)

@asyncio.coroutine
def async_setup(hass, config):
    """Register the service."""
    config = config.get(DOMAIN, {})

    @asyncio.coroutine
    def change_work_mode(service):
        yield from _change_work_mode(hass, service)

    @asyncio.coroutine
    def change_sound_mode(service):
        yield from _change_sound_mode(hass, service)

    @asyncio.coroutine
    def exec_command(service):
        yield from _exec_command(hass, service)

    # register services
    hass.services.async_register(
        DOMAIN, 'change_work_mode', change_work_mode)
    hass.services.async_register(
        DOMAIN, 'change_sound_mode', change_sound_mode)
    hass.services.async_register(
        DOMAIN, 'exec_command', exec_command)

    # temporarily suppress all kernel logging to the console
    os.system("su -c 'dmesg -n 1'")
    # set permissions to /dev/ttyS0
    os.system("su -c 'chmod 666 /dev/ttyS0'")
    # disable tone on start
    # os.system(r'su -c "stty -F /dev/ttyS0 9600 && echo COM+TONEOFF\r\n > /dev/ttyS0"')
    # set aux mode on start
    os.system(r'su -c "stty -F /dev/ttyS0 9600 && echo COM+MAX\r\n > /dev/ttyS0"')
    return True


@asyncio.coroutine
def _change_sound_mode(hass, call):
    # set the mode
    if "mode" not in call.data:
        _LOGGER.error("No mode in call")
        return

    mode = call.data['mode']
    if mode not in ("NORMAL", "BOOST", "TREBLE", "POP", "ROCK", "CLASSIC", "JAZZ", "DANCE", "R&P"):
        _LOGGER.error("Unrecognized mode in call: " + mode)
        return
    comm = r'su -c "stty -F /dev/ttyS0 9600 && echo COM+SETEQ{}\r\n > /dev/ttyS0"'.format(mode)
    os.system(comm)


def set_bt_mode():
    comm = r'su -c "stty -F /dev/ttyS0 9600 && echo COM+MBT\r\n > /dev/ttyS0"'
    os.system(comm)


@asyncio.coroutine
def _change_work_mode(hass, call):
    # set the mode
    if "mode" not in call.data:
        _LOGGER.error("No mode in call")
        return

    from threading import Timer
    mode = call.data['mode']
    if mode not in ("BT", "AX"):
        _LOGGER.error("Unrecognized mode in call: " + mode)
        return
    if mode == "BT":
        yield from hass.services.async_call('ais_ai_service', 'say_it', {"text": "Głośnik w trybie Bluetooth "})
        # change 2 seconds after click
        t = Timer(2, set_bt_mode)
        t.start()
    else:
        comm = r'su -c "stty -F /dev/ttyS0 9600 && echo COM+MAX\r\n > /dev/ttyS0"'
        os.system(comm)
        # say 2 seconds after change
        import time
        time.sleep(2)
        yield from hass.services.async_call('ais_ai_service', 'say_it', {"text": "Głośnik w trybie AUX-IN "})


@asyncio.coroutine
def _exec_command(hass, call):
    if "command" not in call.data:
        _LOGGER.error("No mode in call")
        return
    command = call.data['command']
    # execute control instruction on amplifier via UART
    comm = r'su -c "stty -F /dev/ttyS0 9600 && echo COM+{}\r\n > /dev/ttyS0"'.format(command)
    os.system(comm)
