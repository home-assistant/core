"""
This module exposes AIS dom via Zeroconf.

For more details about this component, please refer to the documentation at
https://sviete.github.io/AIS-docs
"""
import logging
import socket
import subprocess
import voluptuous as vol

from homeassistant.ais_dom import ais_global
from homeassistant import util
from homeassistant.const import (EVENT_HOMEASSISTANT_STOP, __version__)

REQUIREMENTS = ['zeroconf==0.21.3']

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['api']
DOMAIN = 'ais_mdns'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({}),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up Zeroconf and make AIS dom discoverable."""
    from zeroconf import Zeroconf, ServiceInfo

    zero_config = Zeroconf()
    host_ip = util.get_local_ip()

    try:
        return_value = subprocess.check_output('getprop net.hostname', shell=True, timeout=15)
        host_name = return_value.strip().decode('utf-8')
    except subprocess.CalledProcessError:
        host_name = socket.gethostname()
    if len(host_name) == 0:
        # get the mac address
        import uuid
        host_name = ''.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff) for i in range(0, 8*6, 8)][::-1])
    if host_name.endswith('.local'):
        host_name = host_name[:-len('.local')]

    hass.states.async_set("sensor.local_host_name", host_name.upper(),
                          {"friendly_name": "Lokalna nazwa hosta", "icon": "mdi:dns"})
    try:
        ip = socket.inet_pton(socket.AF_INET, host_ip)
    except socket.error:
        ip = socket.inet_pton(socket.AF_INET6, host_ip)
    try:
        gate_id = ais_global.get_sercure_android_id_dom()
    except:
        gate_id = 'xxx'

    params = {
        'version': __version__,
        'company_url': "https://ai-speaker.com",
        'gate_id': gate_id,
    }

    # HASS
    hass_info = ServiceInfo("_home-assistant._tcp.local.",
                            host_name + "._home-assistant._tcp.local.",
                            ip, 8180, 0, 0,
                            params, host_name + ".local.")

    zero_config.register_service(hass_info)

    # HTTP
    http_info = ServiceInfo("_http._tcp.local.",
                            host_name + "._http._tcp.local.",
                            ip, 8180, 0, 0,
                            params, host_name + ".local.")

    zero_config.register_service(http_info)

    # MQTT is moved to the android
    # mqtt_info = ServiceInfo("_mqtt._tcp.local.",
    #                         host_name + "._mqtt._tcp.local.",
    #                         ip, 1883, 0, 0,
    #                         params, host_name + ".local.")
    #
    # zero_config.register_service(mqtt_info)

    # FTP
    ftp_info = ServiceInfo("_ftp._tcp.local.",
                           host_name + "._ftp._tcp.local.",
                           ip, 1024, 0, 0,
                           params, host_name + ".local.")

    zero_config.register_service(ftp_info)


    def stop_zeroconf(event):
        """Stop Zeroconf."""
        zero_config.unregister_service(hass_info)
        zero_config.unregister_service(http_info)
        # zero_config.unregister_service(mqtt_info)
        zero_config.unregister_service(ftp_info)
        zero_config.close()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_zeroconf)

    return True
