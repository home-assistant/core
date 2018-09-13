"""Utils for Molohub."""
import logging
import random
import socket

import yaml

from .const import TCP_PACK_HEADER_LEN

LOGGER = logging.getLogger(__package__)


def get_mac_addr():
    """Get local mac address."""
    import uuid
    node = uuid.getnode()
    mac = uuid.UUID(int=node).hex[-12:]
    return mac


def dns_open(host):
    """Get ip from hostname."""
    try:
        ip_host = socket.gethostbyname(host)
    except socket.error:
        return None

    return ip_host


def len_to_byte(length):
    """Write length integer to bytes buffer."""
    return length.to_bytes(TCP_PACK_HEADER_LEN, byteorder='little')


def byte_to_len(byteval):
    """Read length integer from bytes."""
    if len(byteval) == TCP_PACK_HEADER_LEN:
        return int.from_bytes(byteval, byteorder='little')
    return 0


def get_rand_char(length):
    """Generate random string by length."""
    _chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghijklmnopqrstuvwxyz"
    return ''.join(random.sample(_chars, length))


def fire_molohub_event(hass, data):
    """Send hass Event message."""
    if not hass:
        return
    hass.bus.fire('molohub_event', data)


def get_local_seed(config_file):
    """Read seed from local file."""
    local_seed = ""
    try:
        with open(config_file, 'r') as file_obj:
            config_data = yaml.load(file_obj)
            if config_data and 'molohub' in config_data:
                if 'localseed' in config_data['molohub']:
                    local_seed = config_data['molohub']['localseed']
    except (EnvironmentError, yaml.YAMLError):
        pass
    return local_seed


def save_local_seed(config_file, local_seed):
    """Save seed to local file."""
    config_data = None
    try:
        with open(config_file, 'r') as rfile:
            config_data = yaml.load(rfile)
    except (EnvironmentError, yaml.YAMLError):
        pass

    if not config_data:
        config_data = {}
        config_data['molohub'] = {}
    try:
        with open(config_file, 'w') as wfile:
            config_data['molohub']['localseed'] = local_seed
            yaml.dump(config_data, wfile, default_flow_style=False)
    except (EnvironmentError, yaml.YAMLError):
        pass
