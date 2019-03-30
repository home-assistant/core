"""Support for Proxmox Virtual Environment."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, CONF_VERIFY_SSL)
from homeassistant.core import callback
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval

REQUIREMENTS = ['proxmoxer==1.0.3']
DOMAIN = 'proxmox'
UPDATE_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)
DATA_PROXMOX_NODES = 'proxmox_nodes'

CONF_REALM = 'realm'
CONF_NODES = 'nodes'
CONF_VMS = 'vms'

DEFAULT_PORT = 8006
DEFAULT_REALM = 'pam'
DEFAULT_VERIFY_SSL = True

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_REALM, default=DEFAULT_REALM): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        vol.Optional(CONF_NODES, default=[]): [cv.string],
        vol.Optional(CONF_VMS, default=[]): [int]
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Proxmox VE component."""
    from proxmoxer.backends.https import AuthenticationError
    conf = config.get(DOMAIN)
    if conf is not None:
        try:
            proxmox = await get_client(conf)
            if proxmox is None:
                _LOGGER.exception("Error connecting to proxmox.")
                return False
            await setup_proxmox(hass, config)
        except AuthenticationError:
            # Error authenticating to Proxmox VE
            _LOGGER.exception("Invalid username or password.")
            return False
    return True


async def get_client(conf):
    """Return Proxmox VE API client."""
    from proxmoxer import ProxmoxAPI
    host = conf[CONF_HOST]
    port = conf[CONF_PORT]
    user = conf[CONF_USERNAME]
    realm = conf[CONF_REALM]
    password = conf[CONF_PASSWORD]
    verify_ssl = conf[CONF_VERIFY_SSL]
    proxmox = ProxmoxAPI(
        host, user=user + '@' + realm, password=password,
        port=port, verify_ssl=verify_ssl)
    return proxmox


@callback
async def setup_proxmox(hass, config):
    """Create entities and load data from Proxmox VE."""
    conf = config.get(DOMAIN)
    await update_data(hass, conf)

    hass.async_create_task(
        discovery.async_load_platform(
            hass, 'binary_sensor', DOMAIN, {}, config))

    async def async_update_proxmox(now):
        await update_data(hass, conf)

    async_track_time_interval(hass, async_update_proxmox, UPDATE_INTERVAL)


async def update_data(hass, conf):
    """Update Proxmox VE data."""
    conf_nodes = conf[CONF_NODES]
    conf_vms = conf[CONF_VMS]
    proxmox = await get_client(conf)
    nodes = proxmox.nodes.get()
    node_dict = {}
    for node in nodes:
        name = node['node']
        if conf_nodes and name not in conf_nodes:
            continue
        node_dict[name] = format_values(node)
        cts = proxmox.nodes(name).lxc.get()
        for item in cts:
            vm_id = item['vmid']
            if conf_vms and int(vm_id) not in conf_vms:
                continue
            item['node'] = name
            key = "{} - {}".format(item['name'], vm_id)
            node_dict[key] = format_values(item)
        vms = proxmox.nodes(name).qemu.get()
        for item in vms:
            vm_id = item['vmid']
            if conf_vms and int(vm_id) not in conf_vms:
                continue
            item['node'] = name
            key = "{} - {}".format(item['name'], vm_id)
            node_dict[key] = format_values(item)
    hass.data[DATA_PROXMOX_NODES] = node_dict


def format_values(item):
    """Convert the data into a human readable format."""
    item['uptime'] = "{:.2f}".format(item['uptime']/86400)
    item['ram_usage'] = "{:.2f}".format(item['mem'] * 100 / item['maxmem'])
    item['disk_usage'] = \
        "{:.2f}".format(int(item['disk']) * 100 / int(item['maxdisk']))
    item['cpu_usage'] = "{:.2f}".format(item['cpu'] * 100)
    item['mem'] = to_gb(item['mem'])
    item['maxmem'] = to_gb(item['maxmem'])
    item['disk'] = to_gb(item['disk'])
    item['maxdisk'] = to_gb(item['maxdisk'])
    return item


def to_gb(byte_value):
    """Convert the given byte value to GB."""
    return "{:.2f}".format(int(byte_value)/1073741824)


def fix_status(hass, item, status):
    """Update cached data with the new status of the vm."""
    data = hass.data[DATA_PROXMOX_NODES]
    item['status'] = status
    data["{} - {}".format(item['name'], item['vmid'])] = item
    hass.data[DATA_PROXMOX_NODES] = data
