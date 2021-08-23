"""
Exposes regular shell commands as services.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/shell_command/
"""
import asyncio

import async_timeout
import logging
import multiprocessing
import os
import platform
import subprocess

import homeassistant.components.ais_dom.ais_global as ais_global
from homeassistant.helpers import aiohttp_client

DOMAIN = "ais_shell_command"
GLOBAL_X = 0
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Register the service."""
    config = config.get(DOMAIN, {})

    async def cec_command(service):
        await _cec_command(hass, service)

    async def change_host_name(service):
        await _change_host_name(hass, service)

    async def execute_command(service):
        await _execute_command(hass, service)

    async def execute_script(service):
        await _execute_script(hass, service)

    async def execute_restart(service):
        await _execute_restart(hass, service)

    async def restart_pm2_service(service):
        await _restart_pm2_service(hass, service)

    async def execute_stop(service):
        await _execute_stop(hass, service)

    async def key_event(service):
        await _key_event(hass, service)

    async def led(service):
        await _led(hass, service)

    async def init_local_sdcard(service):
        await _init_local_sdcard(hass, service)

    async def flush_logs(service):
        await _flush_logs(hass, service)

    async def ssh_remote_access(service):
        await _ssh_remote_access(hass, service)

    async def set_ais_secure_android_id_dom(service):
        await _set_ais_secure_android_id_dom(hass, service)

    async def hdmi_control_disable(service):
        await _hdmi_control_disable(hass, service)

    async def change_wm_overscan(service):
        await _change_wm_overscan(hass, service)

    async def disable_irda_remote(service):
        await _disable_irda_remote(hass, service)

    async def change_remote_access(service):
        await _change_remote_access(hass, service)

    async def set_scaling_governor(service):
        await _set_scaling_governor(hass, service)

    async def set_io_scheduler(service):
        await _set_io_scheduler(hass, service)

    async def set_clock_display_text(service):
        await _set_clock_display_text(hass, service)

    async def install_zwave(service):
        await _install_zwave(hass, service)

    async def start_sip_server(service):
        await _start_sip_server(hass, service)

    # register services
    hass.services.async_register(DOMAIN, "change_host_name", change_host_name)
    hass.services.async_register(DOMAIN, "cec_command", cec_command)
    hass.services.async_register(DOMAIN, "execute_command", execute_command)
    hass.services.async_register(DOMAIN, "execute_script", execute_script)
    hass.services.async_register(DOMAIN, "execute_restart", execute_restart)
    hass.services.async_register(DOMAIN, "restart_pm2_service", restart_pm2_service)
    hass.services.async_register(DOMAIN, "execute_stop", execute_stop)
    hass.services.async_register(DOMAIN, "key_event", key_event)
    hass.services.async_register(DOMAIN, "led", led)
    hass.services.async_register(
        DOMAIN, "set_ais_secure_android_id_dom", set_ais_secure_android_id_dom
    )
    hass.services.async_register(DOMAIN, "init_local_sdcard", init_local_sdcard)
    hass.services.async_register(DOMAIN, "flush_logs", flush_logs)
    hass.services.async_register(DOMAIN, "change_remote_access", change_remote_access)
    hass.services.async_register(DOMAIN, "ssh_remote_access", ssh_remote_access)
    hass.services.async_register(DOMAIN, "hdmi_control_disable", hdmi_control_disable)
    hass.services.async_register(DOMAIN, "change_wm_overscan", change_wm_overscan)
    hass.services.async_register(DOMAIN, "disable_irda_remote", disable_irda_remote)
    hass.services.async_register(DOMAIN, "set_scaling_governor", set_scaling_governor)
    hass.services.async_register(DOMAIN, "set_io_scheduler", set_io_scheduler)
    hass.services.async_register(DOMAIN, "install_zwave", install_zwave)
    hass.services.async_register(DOMAIN, "start_sip_server", start_sip_server)
    if ais_global.has_front_clock():
        hass.services.async_register(
            DOMAIN, "set_clock_display_text", set_clock_display_text
        )
        comm = r'su -c "echo AIS > /sys/class/fd655/panel"'
        await _run(comm)
    return True


async def _run(cmd):
    cmd_process = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await cmd_process.communicate()

    if stdout:
        _LOGGER.info("stdout %s", stdout.decode())
    if stderr:
        _LOGGER.info("stderr %s", stderr.decode())


async def _cec_command(hass, call):
    if "command" not in call.data:
        return
    if not ais_global.has_root():
        return
    command = call.data["command"]
    cec_cmd = "su -c 'echo " + command + " > /sys/class/cec/cmd'"
    await _run(cec_cmd)


async def _change_host_name(hass, call):
    if "hostname" not in call.data:
        return
    if not ais_global.has_root():
        return
    new_host_name = call.data["hostname"]
    file = "/data/data/pl.sviete.dom/.ais/ais-hostname"
    command = 'echo "net.hostname = ' + new_host_name + '" > ' + file

    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)  # nosec
    process.wait()
    command = 'su -c "/data/data/pl.sviete.dom/.ais/run_as_root.sh"'
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)  # nosec
    process.wait()


async def _change_remote_access(hass, call):
    text = " zdalny dostęp do bramki z Internetu"
    access = hass.states.get("input_boolean.ais_remote_access").state
    # not allow to off on demo
    gate_id = ais_global.get_sercure_android_id_dom()
    if (
        ais_global.get_sercure_android_id_dom() in ("dom-demo", "dom-dev")
        and access != "on"
    ):
        await hass.services.async_call(
            "ais_ai_service",
            "say_it",
            {"text": "Nie można zatrzymać zdalnego dostępu na instancji demo."},
        )
        hass.states.async_set("input_boolean.ais_remote_access", "on")
        return
    if access == "on":
        text = "Aktywuje " + text
    else:
        text = "Zatrzymuje " + text

    await hass.services.async_call("ais_ai_service", "say_it", {"text": text})
    _LOGGER.info(text)

    if access == "on":
        if not os.path.isfile("/data/data/pl.sviete.dom/files/home/.cloudflared/cert.pem"):
            await _run("mkdir -p /data/data/pl.sviete.dom/files/home/.cloudflared")
            # delete old tunnel
            await _run("pm2 delete tunnel")
            with async_timeout.timeout(20):
                web_session = aiohttp_client.async_get_clientsession(hass)
                # store file
                async with web_session.get("https://ai-speaker.com/ota/ais_cloudflared") as resp:
                    if resp.status == 200:
                        body = await resp.read()
                        f = open('/data/data/pl.sviete.dom/files/home/.cloudflared/cert.pem', mode='wb')
                        f.write(body)
                        f.close()
            # # create named tunnel
            # await _run("/data/data/pl.sviete.dom/files/usr/bin/cloudflared --origincert "
            #            "/data/data/pl.sviete.dom/files/home/.cloudflared/cert.pem tunnel delete -f " + gate_id)
            # await _run("/data/data/pl.sviete.dom/files/usr/bin/cloudflared --origincert "
            #            "/data/data/pl.sviete.dom/files/home/.cloudflared/cert.pem tunnel create " + gate_id)
            # # rename credentials file
            # await _run("mv /data/data/pl.sviete.dom/files/home/.cloudflared/*.json "
            #            "/data/data/pl.sviete.dom/files/home/.cloudflared/key.json")
            #
            # # create config.yaml
            # f = open('/data/data/pl.sviete.dom/files/home/.cloudflared/config.yaml', mode='w')
            # f.write("tunnel: " + gate_id + "\n")
            # f.write("credentials-file: /data/data/pl.sviete.dom/files/home/.cloudflared/key.json\n")
            # f.write("ingress:\n")
            # f.write("  - hostname: " + gate_id + ".paczka.pro\n")
            # f.write("    service: http://localhost:8180\n")
            # f.write("  - service: http_status:404")
            # f.close()
            #
            # # route traffic
            # await _run("/data/data/pl.sviete.dom/files/usr/bin/cloudflared --origincert "
            #            "/data/data/pl.sviete.dom/files/home/.cloudflared/cert.pem tunnel route dns -f " + gate_id
            #            + " " + gate_id + ".paczka.pro")

            # # delete cert file
            # await _run("rm /data/data/pl.sviete.dom/files/home/.cloudflared/cert.pem")

        await _run(
            "pm2 restart tunnel || pm2 start /data/data/pl.sviete.dom/files/usr/bin/cloudflared"
            " --name tunnel --output /dev/null --error /dev/null"
            " --restart-delay=150000 -- --hostname http://{}.paczka.pro --url http://localhost:8180".format(
                gate_id
            )
        )
    else:
        await _run("pm2 delete tunnel && pm2 save")
        await _run("rm /data/data/pl.sviete.dom/files/home/.cloudflared/*")


async def _hdmi_control_disable(hass, call):
    if not ais_global.has_root():
        return
    comm = r'su -c "settings put global hdmi_control_enabled 0"'
    await _run(comm)


async def _change_wm_overscan(hass, call):
    if "value" not in call.data:
        return
    if not ais_global.has_root():
        return
    new_value = call.data["value"]
    cl = 0
    ct = 0
    cr = 0
    cb = 0

    try:
        overscan = subprocess.check_output(
            "su -c \"dumpsys display  | grep -o 'overscan.*' | cut -d')' -f1 | rev | cut -d'(' -f1 | rev\"",
            shell=True,  # nosec
            timeout=10,
        )
        overscan = overscan.decode("utf-8").replace("\n", "")
        if "," in overscan:
            cl = int(overscan.split(",")[0])
            ct = int(overscan.split(",")[1])
            cr = int(overscan.split(",")[2])
            cb = int(overscan.split(",")[3])
    except Exception as e:
        _LOGGER.warning("Can't get current overscan %s", e)

    # [reset|LEFT,TOP,RIGHT,BOTTOM]
    if new_value == "reset":
        comm = r'su -c "wm overscan reset"'
    elif new_value == "left":
        comm = (
            r'su -c "wm overscan '
            + str(int(cl) - 3)
            + ","
            + str(ct)
            + ","
            + str(cr)
            + ","
            + str(cb)
            + '"'
        )
    elif new_value == "top":
        comm = (
            r'su -c "wm overscan '
            + str(cl)
            + ","
            + str(int(ct) - 3)
            + ","
            + str(cr)
            + ","
            + str(cb)
            + '"'
        )
    elif new_value == "right":
        comm = (
            r'su -c "wm overscan '
            + str(cl)
            + ","
            + str(ct)
            + ","
            + str(int(cr) - 3)
            + ","
            + str(cb)
            + '"'
        )
    elif new_value == "bottom":
        comm = (
            r'su -c "wm overscan '
            + str(cl)
            + ","
            + str(ct)
            + ","
            + str(cr)
            + ","
            + str(int(cb) - 3)
            + '"'
        )
    elif new_value == "-left":
        comm = (
            r'su -c "wm overscan '
            + str(int(cl) + 3)
            + ","
            + str(ct)
            + ","
            + str(cr)
            + ","
            + str(cb)
            + '"'
        )
    elif new_value == "-top":
        comm = (
            r'su -c "wm overscan '
            + str(cl)
            + ","
            + str(int(ct) + 3)
            + ","
            + str(cr)
            + ","
            + str(cb)
            + '"'
        )
    elif new_value == "-right":
        comm = (
            r'su -c "wm overscan '
            + str(cl)
            + ","
            + str(ct)
            + ","
            + str(int(cr) + 3)
            + ","
            + str(cb)
            + '"'
        )
    elif new_value == "-bottom":
        comm = (
            r'su -c "wm overscan '
            + str(cl)
            + ","
            + str(ct)
            + ","
            + str(cr)
            + ","
            + str(int(cb) + 3)
            + '"'
        )
    else:
        _LOGGER.error(f"Value for overscan provided {new_value}")
        return
    await _run(comm)


async def _ssh_remote_access(hass, call):
    access = "on"
    if "access" in call.data:
        access = call.data["access"]
    gate_id = "ssh-" + hass.states.get("sensor.ais_secure_android_id_dom").state
    if access == "on":
        await _run(
            "pm2 restart ssh-tunnel || pm2 start /data/data/pl.sviete.dom/files/usr/bin/cloudflared"
            " --name ssh-tunnel --output /dev/null --error /dev/null"
            " --restart-delay=150000 -- --hostname http://{}.paczka.pro --url http://localhost:8888".format(
                gate_id
            )
        )
        _LOGGER.warning(
            "You have SSH access to gate on http://" + gate_id + ".paczka.pro"
        )
    else:
        await _run("pm2 delete ssh-tunnel && pm2 save")


async def _key_event(hass, call):
    if "key_code" not in call.data:
        return
    if not ais_global.has_root():
        return
    key_code = call.data["key_code"]

    subprocess.Popen(
        "su -c 'input keyevent " + key_code + "'",
        shell=True,  # nosec
        stdout=None,
        stderr=None,
    )


async def _led(hass, call):
    if "brightness" not in call.data:
        return
    if not ais_global.has_root():
        return
    brightness = call.data["brightness"]

    script = str(os.path.dirname(__file__))
    script += "/scripts/led.sh"

    subprocess.Popen(
        "su -c ' " + script + " " + str(brightness) + "'",
        shell=True,  # nosec
        stdout=None,
        stderr=None,
    )


async def _set_ais_secure_android_id_dom(hass, call):
    # the G_AIS_SECURE_ANDROID_ID_DOM is set only in one place ais_global
    hass.states.async_set(
        "sensor.ais_secure_android_id_dom",
        ais_global.get_sercure_android_id_dom(),
        {
            "friendly_name": "Unikalny identyfikator bramki",
            "icon": "mdi:account-card-details",
        },
    )

    # check the gate model
    hass.states.async_set("sensor.ais_gate_model", ais_global.get_ais_gate_model())


async def _init_local_sdcard(hass, call):
    if not ais_global.has_root():
        return
    script = str(os.path.dirname(__file__))
    script += "/scripts/init_local_sdcard.sh"
    subprocess.Popen(script, shell=True, stdout=None, stderr=None)  # nosec


async def _execute_command(hass, call):
    command = None
    ret_entity = None
    friendly_name = None
    icon = None

    if "command" not in call.data:
        return
    else:
        command = call.data["command"]
    _LOGGER.info("execute_command: " + command)
    if "entity_id" in call.data:
        ret_entity = call.data["entity_id"]
    if "friendly_name" in call.data:
        friendly_name = call.data["friendly_name"]
    if "icon" in call.data:
        icon = call.data["icon"]

    process = subprocess.Popen(
        command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE  # nosec
    )
    output, err = process.communicate()
    if ret_entity is not None:
        hass.states.async_set(
            ret_entity, output, {"friendly_name": friendly_name, "icon": icon}
        )


async def _execute_script(hass, call):
    if "script" not in call.data:
        return
    script = call.data["script"]

    if script == "reset_usb.sh":
        # take the full path
        script = str(os.path.dirname(__file__))
        script += "/scripts/reset_usb.sh"
        ais_global.G_USB_INTERNAL_MIC_RESET = True

    process = subprocess.Popen(script, shell=True, stdout=subprocess.PIPE)  # nosec
    process.wait()


async def _execute_restart(hass, call):
    if not ais_global.has_root():
        return

    subprocess.Popen("su -c reboot", shell=True, stdout=None, stderr=None)  # nosec


async def _restart_pm2_service(hass, call):
    service = call.data["service"]

    await hass.services.async_call(
        "ais_ai_service", "say_it", {"text": "Restartuje serwis " + service}
    )
    cmd_to_run = "pm2 restart " + service
    if service == "zwave":
        cmd_to_run = (
            "pm2 restart zwave || pm2 start /data/data/pl.sviete.dom/files/home/zwavejs2mqtt/server/bin/www.js "
            "--name zwave --output /dev/null --error /dev/null --restart-delay=120000"
        )
    elif service == "zigbee":
        cmd_to_run = (
            "pm2 restart zigbee || cd /data/data/pl.sviete.dom/files/home/zigbee2mqtt; pm2 start index.js "
            "--name zigbee --output /dev/null --error /dev/null --restart-delay=120000"
        )
    await _run(cmd_to_run)


async def _execute_stop(hass, call):
    if not ais_global.has_root():
        return

    subprocess.Popen("su -c 'reboot -p'", shell=True, stdout=None, stderr=None)  # nosec


async def _flush_logs(hass, call):
    # pm2
    await _run("pm2 flush")
    await _run("rm /data/data/pl.sviete.dom/files/home/.pm2/logs/*.log")

    # pip cache
    await _run("rm -rf /data/data/pl.sviete.dom/files/home/.cache/pip")
    # recorder.purge if recorder exists
    if hass.services.has_service("recorder", "purge"):
        keep_days = 5
        if ais_global.G_DB_SETTINGS_INFO is not None:
            # take keep days from settings
            if "dbKeepDays" in ais_global.G_DB_SETTINGS_INFO:
                keep_days = int(ais_global.G_DB_SETTINGS_INFO["dbKeepDays"])
            # allow to store only 5 days in memory
            if "dbUrl" in ais_global.G_DB_SETTINGS_INFO:
                if ais_global.G_DB_SETTINGS_INFO["dbUrl"].startswith(
                    "sqlite:///:memory:"
                ):
                    keep_days = 5

        await hass.services.async_call(
            "recorder", "purge", {"keep_days": keep_days, "repack": True}
        )


async def _disable_irda_remote(hass, call):
    if not ais_global.has_root():
        return
    # aml_keypad -> event0 irda remote
    comm = r'su -c "rm -rf /dev/input/event0"'
    await _run(comm)
    # cec_input -> event2 hdmi cec
    comm = r'su -c "rm -rf /dev/input/event2"'
    await _run(comm)
    # gpio_keypad -> event0 - button behind the AV port can be used it in the future :)


async def _set_scaling_governor(hass, call):
    if (
        not ais_global.has_root()
        or multiprocessing.cpu_count() > 5
        or "4.9.113" in platform.uname()
    ):
        return
    # /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors
    scaling_available_governors = ["hotplug", "interactive", "performance"]

    # interactive is default scaling
    scaling = "interactive"
    if "scaling" in call.data:
        scaling = call.data["scaling"]
    # default powersave freq
    # /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies
    freq = "1000000"
    if scaling == "performance":
        freq = "1200000"

    if scaling in scaling_available_governors:
        comm = (
            r'su -c "echo '
            + scaling
            + ' > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"'
        )
        await _run(comm)

    comm = (
        r'su -c "echo '
        + freq
        + ' > /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq"'
    )
    await _run(comm)


async def _set_io_scheduler(hass, call):
    if not ais_global.has_root():
        return
    # /sys/block/mmcblk0/queue/scheduler
    available_io_schedulers = ["noop", "deadline", "cfq"]

    # noop is now default scheduler
    scheduler = "noop"
    if "scheduler" in call.data:
        scheduler = call.data["scheduler"]

    if scheduler in available_io_schedulers:
        comm = r'su -c "echo ' + scheduler + ' > /sys/block/mmcblk0/queue/scheduler"'
        await _run(comm)


async def _set_clock_display_text(hass, call):
    if not ais_global.has_root():
        return
    text = call.data["text"]

    comm = r'su -c "echo ' + text + ' > /sys/class/fd655/panel"'
    await _run(comm)


async def _install_zwave(hass, call):
    script = str(os.path.dirname(__file__))
    script += "/scripts/install_zwave.sh"

    subprocess.Popen(
        "su -c ' " + script + " " + "'",
        shell=True,  # nosec
        stdout=None,
        stderr=None,
    )


async def _start_sip_server(hass, call):
    if not ais_global.has_root():
        return

    comm = r"su -c 'am start -n com.aispeaker.sipserver/.USipServerActivity --ez start_from_ais true'"
    await _run(comm)
