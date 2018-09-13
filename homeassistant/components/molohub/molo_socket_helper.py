"""Socket helper class for Molohub."""
import platform

from .const import CONFIG_FILE_NAME
from .utils import get_local_seed, get_mac_addr, get_rand_char, save_local_seed


class MoloSocketHelper:
    """Socket helper class for Molohub."""

    @classmethod
    def molo_auth(cls, client_version, hass, ha_version):
        """Construct register authorization packet."""
        payload = dict()
        payload['ClientId'] = ''
        payload['OS'] = platform.platform()
        payload['PyVersion'] = platform.python_version()
        payload['ClientVersion'] = client_version
        payload['HAVersion'] = ha_version

        payload['MacAddr'] = get_mac_addr()
        local_seed = get_mac_addr()
        local_seed_saved = get_local_seed(hass.config.path(CONFIG_FILE_NAME))
        if local_seed_saved:
            local_seed = local_seed_saved
        else:
            save_local_seed(hass.config.path(CONFIG_FILE_NAME), local_seed)
        payload['LocalSeed'] = local_seed

        body = dict()
        body['Type'] = 'Auth'
        body['Payload'] = payload
        return body

    @classmethod
    def req_tunnel(cls, protocol, hostname, subdomain, remote_port, clientid):
        """Construct request tunnel packet."""
        payload = dict()
        payload['ReqId'] = get_rand_char(8)
        payload['Protocol'] = protocol
        payload['Hostname'] = hostname
        payload['Subdomain'] = subdomain
        payload['HttpAuth'] = ''
        payload['RemotePort'] = remote_port
        payload['MacAddr'] = get_mac_addr()
        if clientid:
            payload['ClientId'] = clientid
        body = dict()
        body['Type'] = 'ReqTunnel'
        body['Payload'] = payload
        return body

    @classmethod
    def reg_proxy(cls, client_id):
        """Construct register proxy packet."""
        payload = dict()
        payload['ClientId'] = client_id
        body = dict()
        body['Type'] = 'RegProxy'
        body['Payload'] = payload
        return body

    @classmethod
    def ping(cls, token, client_status):
        """Construct ping packet."""
        payload = dict()
        body = dict()
        if token:
            payload['Token'] = token
        if client_status and client_status:
            payload['Status'] = client_status
        body['Type'] = 'Ping'
        body['Payload'] = payload
        return body
