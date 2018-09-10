"""
Exposes regular shell commands as services.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/shell_command/
"""
from homeassistant.const import (CONF_IP_ADDRESS, CONF_MAC)
import asyncio
import logging
import os
import homeassistant.ais_dom.ais_global as ais_global
REQUIREMENTS = ['requests_futures']
DOMAIN = 'ais_shell_command'
GLOBAL_X = 0
_LOGGER = logging.getLogger(__name__)

@asyncio.coroutine
def async_setup(hass, config):
    """Register the service."""
    config = config.get(DOMAIN, {})

    @asyncio.coroutine
    def change_host_name(service):
        yield from _change_host_name(hass, service)

    @asyncio.coroutine
    def execute_command(service):
        yield from _execute_command(hass, service)

    @asyncio.coroutine
    def execute_script(service):
        yield from _execute_script(hass, service)

    @asyncio.coroutine
    def execute_upgrade(service):
        yield from _execute_upgrade(hass, service)

    @asyncio.coroutine
    def key_event(service):
        yield from _key_event(hass, service)

    @asyncio.coroutine
    def scan_network_for_devices(service):
        yield from _scan_network_for_devices(hass, service)

    @asyncio.coroutine
    def scan_device(service):
        yield from _scan_device(hass, service)

    @asyncio.coroutine
    def show_network_devices_info(service):
        yield from _show_network_devices_info(hass, service)

    @asyncio.coroutine
    def led(service):
        yield from _led(hass, service)

    @asyncio.coroutine
    def init_local_sdcard(service):
        yield from _init_local_sdcard(hass, service)

    # register services
    hass.services.async_register(
        DOMAIN, 'change_host_name', change_host_name)
    hass.services.async_register(
        DOMAIN, 'execute_command', execute_command)
    hass.services.async_register(
        DOMAIN, 'execute_script', execute_script)
    hass.services.async_register(
        DOMAIN, 'execute_upgrade', execute_upgrade)
    hass.services.async_register(
        DOMAIN, 'key_event', key_event)
    hass.services.async_register(
        DOMAIN, 'scan_network_for_devices', scan_network_for_devices)
    hass.services.async_register(
        DOMAIN, 'scan_device', scan_device)
    hass.services.async_register(
        DOMAIN, 'show_network_devices_info', show_network_devices_info)
    hass.services.async_register(
        DOMAIN, 'led', led)
    hass.services.async_register(
        DOMAIN, 'init_local_sdcard', init_local_sdcard)
    return True


@asyncio.coroutine
def _change_host_name(hass, call):
    new_host_name = hass.states.get('input_text.new_host_name').state
    file = '/data/data/pl.sviete.dom/.ais/ais-hostname'
    command = 'echo "net.hostname = ' + new_host_name + '" > ' + file
    import subprocess
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    process.wait()
    command = 'sudo /data/data/pl.sviete.dom/.ais/run_as_root.sh'
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    process.wait()


@asyncio.coroutine
def _key_event(hass, call):
    if ("key_code" not in call.data):
        _LOGGER.error("No key_code")
        return
    key_code = call.data["key_code"]
    import subprocess
    subprocess.Popen(
        "su -c 'input keyevent " + key_code + "'",
        shell=True, stdout=None, stderr=None)


@asyncio.coroutine
def _led(hass, call):
    if ("brightness" not in call.data):
        _LOGGER.error("No brightness provided")
        return
    brightness = call.data["brightness"]

    script = str(os.path.dirname(__file__))
    script += '/scripts/led.sh'

    import subprocess
    subprocess.Popen(
        "su -c ' ." + script + " " + str(brightness) + "'",
        shell=True, stdout=None, stderr=None)


@asyncio.coroutine
def _init_local_sdcard(hass, call):
    script = str(os.path.dirname(__file__))
    script += '/scripts/init_local_sdcard.sh'
    import subprocess
    subprocess.Popen(script, shell=True, stdout=None, stderr=None)


@asyncio.coroutine
def _execute_command(hass, call):
    command = None
    ret_entity = None
    friendly_name = None
    icon = None

    if ("command" not in call.data):
        _LOGGER.error("No command")
        return
    else:
        command = call.data["command"]
    if ("entity_id" not in call.data):
        _LOGGER.debug("No entity_id to return the output")
    else:
        ret_entity = call.data["entity_id"]
    if ("friendly_name" not in call.data):
        _LOGGER.debug("No friendly_name to set in returning output")
    else:
        friendly_name = call.data["friendly_name"]
    if ("icon" not in call.data):
        _LOGGER.debug("No icon to set in returning output")
    else:
        icon = call.data["icon"]

    import subprocess
    process = subprocess.Popen(
        command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, err = process.communicate()
    _LOGGER.error("err: " + str(err))
    if ret_entity is not None:
        hass.states.async_set(ret_entity, output, {
          "friendly_name": friendly_name,
          "icon": icon
        })


@asyncio.coroutine
def _execute_script(hass, call):
    if ("script" not in call.data):
        _LOGGER.error("No script")
        return
    script = call.data["script"]
    import subprocess
    process = subprocess.Popen(script, shell=True, stdout=subprocess.PIPE)
    process.wait()
    _LOGGER.info("_execute_script, return: " + str(process.returncode))


@asyncio.coroutine
def _execute_upgrade(hass, call):
    # check the status of the sensor to choide the correct upgrade method
    state = hass.states.get('sensor.version_info')
    reinstall_android_app = state.attributes.get('reinstall_android_app')
    apt = state.attributes.get('apt')
    if apt is not None and apt != "":
        _LOGGER.info("We have apt dependencies " + str(apt))
        try:
            apt_script = str(os.path.dirname(__file__))
            apt_script += '/scripts/apt_install.sh'
            f = open(str(apt_script), "w")
            f.write("#!/data/data/pl.sviete.dom/files/usr/bin/sh" + os.linesep)
            for l in apt.split(","):
                f.write(l + os.linesep)
            f.close()
            import subprocess
            apt_process = subprocess.Popen(apt_script, shell=True, stdout=None, stderr=None)
            apt_process.wait()
            _LOGGER.info("apt_install, return: " + str(apt_process.returncode))
        except Exception as e:
            _LOGGER.error("Can't install apt dependencies, error: " + str(e))
    else:
        _LOGGER.info("No apt dependencies this time!")

    import subprocess
    if reinstall_android_app is None or reinstall_android_app is False:
        # partial update (without android app)
        script = str(os.path.dirname(__file__))
        script += '/scripts/upgrade_ais.sh'
        process = subprocess.Popen(script, shell=True, stdout=subprocess.PIPE)
        process.wait()
        _LOGGER.info("_execute_upgrade, return: " + str(process.returncode))
        yield from hass.services.async_call('homeassistant', 'restart')
    else:
        # full update
        script = str(os.path.dirname(__file__))
        script += '/scripts/upgrade_ais_full.sh'
        process = subprocess.Popen(script, shell=True, stdout=subprocess.PIPE)
        process.wait()
        _LOGGER.info("_execute_upgrade, return: " + str(process.returncode))
        yield from hass.services.async_call('homeassistant', 'stop')


@asyncio.coroutine
def _show_network_devices_info(hass, call):
    import homeassistant.ais_dom.sensor.ais_device_search_mqtt as dsm
    info = dsm.get_text()
    hass.states.async_set(
        'sensor.network_devices_info_value', '', {
            'custom_ui_state_card': 'state-card-robot-disco',
            'text': info
        })


@asyncio.coroutine
def _scan_device(hass, call):
    if ("url" not in call.data):
        _LOGGER.error("No url")
        return
    url = call.data["url"]
    url_a = call.data["url_a"]
    from requests_futures.sessions import FuturesSession
    from urllib.parse import urlparse
    import homeassistant.ais_dom.sensor.ais_device_search_mqtt as dsm
    session = FuturesSession()

    def bg_cb(sess, resp):
        try:
            # parse the json storing the result on the response object
            json_ws_resp = resp.json()
            hostname = urlparse(resp.url).hostname
            name = json_ws_resp["Status"]["FriendlyName"][0]
            #ip = json_ws_resp["StatusNET"]["IPAddress"]
            dsm.NET_DEVICES.append("#" + name + ", http://" + hostname + ':80')
            info = dsm.get_text()
            hass.states.async_set(
                'sensor.network_devices_info_value', '', {
                    'custom_ui_state_card': 'state-card-robot-disco',
                    'text': info
                })
        except Exception:
            pass

    def bg_cb_a(sess, resp):
        try:
            # parse the json storing the result on the response object
            json_ws_resp = resp.json()
            model = json_ws_resp["Model"]
            manufacturer = json_ws_resp["Manufacturer"]
            ip = json_ws_resp["IPAddressIPv4"]
            mac = json_ws_resp["MacWlan0"]
            dsm.DOM_DEVICES.append(
                "#" + model + " " + manufacturer + ", https://" + ip + ':8123')
            info = dsm.get_text()
            hass.states.async_set(
                'sensor.network_devices_info_value', '', {
                    'custom_ui_state_card': 'state-card-robot-disco',
                    'text': info
                })
            # add the device to the speakers lists
            hass.async_add_job(
                hass.services.async_call(
                    'ais_cloud', 'get_players', {
                        'device_name':  model + " " + manufacturer
                        + "(" + ip + ")",
                        CONF_IP_ADDRESS: ip,
                        CONF_MAC: mac
                    }))
        except Exception:
            pass

    session.get(url, background_callback=bg_cb)
    session.get(url_a, background_callback=bg_cb_a)
    hass.async_add_job(
        hass.services.async_call(
            'ais_shell_command', 'scan_network_for_devices'))


@asyncio.coroutine
def _scan_network_for_devices(hass, call):
    import homeassistant.ais_dom.sensor.ais_device_search_mqtt as dsm
    global GLOBAL_X
    GLOBAL_MY_IP = ais_global.get_my_global_ip()
    info = ""
    if (GLOBAL_X == 0):
        GLOBAL_X += 1
        # clear the value
        dsm.MQTT_DEVICES = []
        dsm.NET_DEVICES = []
        dsm.DOM_DEVICES = []
        # dsm.NET_DEVICES.append("*Twoje IP, " + GLOBAL_MY_IP)
        hass.states.async_set('sensor.network_devices_info_value', '', {
            'custom_ui_state_card': 'state-card-robot-disco',
            'text': '*wykrywam, to może potrwać kilka minut...'
        })

        # send the message to all robots in network
        yield from hass.services.async_call('mqtt', 'publish', {
            'topic': 'cmnd/dom/status',
            'payload': 0
        })
        yield from hass.services.async_call(
            'ais_shell_command', 'scan_network_for_devices')
    # 256
    elif (GLOBAL_X > 0 and GLOBAL_X < 256):
        GLOBAL_X += 1
        rest_url = "http://{}.{}/cm?cmnd=status"
        url = rest_url.format(GLOBAL_MY_IP.rsplit('.', 1)[0], str(GLOBAL_X))
        info = "!sprawdzam " + GLOBAL_MY_IP.rsplit('.', 1)[0]
        info += "." + str(GLOBAL_X) + "\n"
        info += dsm.get_text()
        hass.states.async_set(
            'sensor.network_devices_info_value', '', {
                'custom_ui_state_card': 'state-card-robot-disco',
                'text': info
            })

        # search android devices
        rest_url_a = "http://{}.{}:8122"
        url_a = rest_url_a.format(
            GLOBAL_MY_IP.rsplit('.', 1)[0], str(GLOBAL_X))

        yield from hass.services.async_call(
            'ais_shell_command', 'scan_device', {
                "url": url,
                "url_a": url_a
            })

    else:
        GLOBAL_X = 0
        hass.states.async_set(
            'sensor.network_devices_info_value', '', {
                'custom_ui_state_card': 'state-card-robot-disco',
                'text': dsm.get_text()
                })
