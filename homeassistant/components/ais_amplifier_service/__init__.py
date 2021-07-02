"""
Exposes Amplifier Srvice on AIS dom device

For more details about this platform, please refer to the documentation at
https://www.ai-speaker.com
"""
import logging
import os

import homeassistant.components.ais_dom.ais_global as ais_global

DOMAIN = "ais_amplifier_service"
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Register the service."""
    config = config.get(DOMAIN, {})

    async def change_work_mode(service):
        await _change_work_mode(hass, service)

    async def change_sound_mode(service):
        await _change_sound_mode(hass, service)

    async def exec_command(service):
        await _exec_command(hass, service)

    async def exec_tonos_command(service):
        await _exec_tonos_command(hass, service)

    async def change_audio_to_mono(service):
        await _change_audio_to_mono(hass, service)

    async def get_audio_mono(service):
        await _get_audio_mono(hass, service)

    async def set_audio_routing(service):
        await _set_audio_routing(hass, service)

    # register services
    hass.services.async_register(DOMAIN, "change_work_mode", change_work_mode)
    hass.services.async_register(DOMAIN, "change_sound_mode", change_sound_mode)
    hass.services.async_register(DOMAIN, "exec_command", exec_command)
    hass.services.async_register(DOMAIN, "change_audio_to_mono", change_audio_to_mono)
    hass.services.async_register(DOMAIN, "get_audio_mono", get_audio_mono)
    hass.services.async_register(DOMAIN, "exec_tonos_command", exec_tonos_command)
    hass.services.async_register(DOMAIN, "set_audio_routing", set_audio_routing)

    # temporarily suppress all kernel logging to the console
    if ais_global.has_root():
        os.system("su -c 'dmesg -n 1'")
        # set permissions to /dev/ttyS0
        os.system("su -c 'chmod 666 /dev/ttyS0'")
        # disable tone on start
        # os.system(r'su -c "stty -F /dev/ttyS0 9600 && echo COM+TONEOFF\r\n > /dev/ttyS0"')
        # set aux mode on start
        os.system(r'su -c "stty -F /dev/ttyS0 9600 && echo COM+MAX\r\n > /dev/ttyS0"')
    return True


async def _change_sound_mode(hass, call):
    # set the mode
    if "mode" not in call.data:
        _LOGGER.error("No mode in call")
        return
    if not ais_global.has_root():
        return

    mode = call.data["mode"]
    if mode not in (
            "NORMAL",
            "BOOST",
            "TREBLE",
            "POP",
            "ROCK",
            "CLASSIC",
            "JAZZ",
            "DANCE",
            "R&P",
    ):
        _LOGGER.error("Unrecognized mode in call: " + mode)
        return
    comm = (
        r'su -c "stty -F /dev/ttyS0 9600 && echo COM+SETEQ{}\r\n > /dev/ttyS0"'.format(
            mode
        )
    )
    os.system(comm)


def set_bt_mode():
    if not ais_global.has_root():
        return
    comm = r'su -c "stty -F /dev/ttyS0 9600 && echo COM+MBT\r\n > /dev/ttyS0"'
    os.system(comm)


async def _change_audio_to_mono(hass, call):
    if "mode" not in call.data:
        mode = hass.states.get("input_boolean.ais_audio_mono").state
    else:
        if call.data["mode"]:
            mode = "on"
        else:
            mode = "off"
    info_text = ""
    if mode == "on":
        if ais_global.has_root():
            comm = r'su -c "settings put system master_mono 1"'
            os.system(comm)
        info_text = "włączony"
    else:
        if ais_global.has_root():
            comm = r'su -c "settings put system master_mono 0"'
            os.system(comm)
        info_text = "wyłączony"

    if ais_global.G_AIS_START_IS_DONE:
        await hass.services.async_call(
            "ais_ai_service", "say_it", {"text": "Dźwięk mono " + info_text}
        )


async def _get_audio_mono(hass, call):
    import subprocess

    try:
        if ais_global.has_root():
            mode = subprocess.check_output(
                'su -c "settings get system master_mono"',
                shell=True,  # nosec
                timeout=10,
            )
            mode = mode.decode("utf-8").replace("\n", "")
        else:
            mode = "0"
        if mode == "1":
            await hass.services.async_call(
                "input_boolean",
                "turn_on",
                {"entity_id": "input_boolean.ais_audio_mono"},
            )
        else:
            await hass.services.async_call(
                "input_boolean",
                "turn_off",
                {"entity_id": "input_boolean.ais_audio_mono"},
            )
    except Exception as e:
        _LOGGER.info("Can't get audio master_mono from system settings! " + str(e))


async def _change_work_mode(hass, call):
    # set the mode
    if "mode" not in call.data:
        _LOGGER.error("No mode in call")
        return
    if not ais_global.has_root():
        return
    from threading import Timer

    mode = call.data["mode"]
    if mode not in ("BT", "AX"):
        _LOGGER.error("Unrecognized mode in call: " + mode)
        return
    if mode == "BT":
        await hass.services.async_call(
            "ais_ai_service", "say_it", {"text": "Głośnik w trybie Bluetooth "}
        )
        # change 2 seconds after click
        t = Timer(2, set_bt_mode)
        t.start()
    else:
        comm = r'su -c "stty -F /dev/ttyS0 9600 && echo COM+MAX\r\n > /dev/ttyS0"'
        os.system(comm)
        # say 2 seconds after change
        import time

        time.sleep(2)
        await hass.services.async_call(
            "ais_ai_service", "say_it", {"text": "Głośnik w trybie AUX-IN "}
        )


async def _exec_command(hass, call):
    if "command" not in call.data:
        _LOGGER.error("No command in call")
        return
    if not ais_global.has_root():
        return
    command = call.data["command"]
    # execute control instruction on amplifier via UART
    comm = r'su -c "stty -F /dev/ttyS0 9600 && echo COM+{}\r\n > /dev/ttyS0"'.format(
        command
    )
    os.system(comm)


async def _exec_tonos_command(hass, call):
    if "command" not in call.data:
        _LOGGER.error("No command in call")
        return
    if not ais_global.has_root():
        return
    command = call.data["command"]
    # execute control instruction on amplifier via UART
    comm = r'su -c "stty -F /dev/ttyS0 115200 && echo {} > /dev/ttyS0 && printf "\x0d" > /dev/ttyS0 && printf "\x0d" ' \
           r'> /dev/ttyS0"'.format(command)
    os.system(comm)


async def _set_audio_routing(hass, call):
    if "routing" not in call.data:
        _LOGGER.error("No routing in call")
        return
    routing = call.data["routing"]
    if routing not in (
            "hdmi",
            "spdif",
            "pcm",
            "jack",
            "all"
    ):
        _LOGGER.error("Unrecognized routing in call: " + routing)
        return
    if routing == "jack":
        routing = "pcm"
    # publish command to frame
    await hass.services.async_call(
        "ais_ai_service",
        "publish_command_to_frame",
        {"key": "setAudioRouting", "val": routing, "ip": "localhost"},
    )


