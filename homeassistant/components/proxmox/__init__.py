"""Support for Proxmox Virtual Environment."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, CONF_VERIFY_SSL)
from homeassistant.core import callback
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

REQUIREMENTS = ['proxmoxer==1.0.3']
DOMAIN = 'proxmox'
ENTITY_ID_FORMAT = DOMAIN + '.{}'
UPDATE_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)
DATA_PROXMOX_NODES = 'proxmox_nodes'
DATA_PROXMOX_CONTROL = 'proxmox_control'
SIGNAL_PROXMOX_UPDATED = 'proxmox_updated'
DEFAULT_PORT = 8006
DEFAULT_REALM = 'pam'
DEFAULT_VERIFY_SSL = True

CONF_REALM = 'realm'
CONF_NODES = 'nodes'
CONF_VMS = 'vms'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_REALM, default=DEFAULT_REALM): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        vol.Optional(CONF_NODES, default=[]): [cv.string],
        vol.Optional(CONF_VMS, default=[]): [int],
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Proxmox VE component."""
    from proxmoxer import ProxmoxAPI
    from proxmoxer.backends.https import AuthenticationError
    conf = config.get(DOMAIN)
    if conf is not None:
        host = conf.get(CONF_HOST)
        port = conf.get(CONF_PORT)
        user = conf.get(CONF_USERNAME)
        realm = conf.get(CONF_REALM)
        password = conf.get(CONF_PASSWORD)
        verify_ssl = conf.get(CONF_VERIFY_SSL)
        try:
            proxmox = ProxmoxAPI(
                host, user=user + '@' + realm, password=password,
                port=port, verify_ssl=verify_ssl)
            await setup_proxmox(hass, proxmox, config)
        except AuthenticationError:
            # Error authenticating to Proxmox VE
            _LOGGER.exception("Invalid username or password.")
            return False
    return True


@callback
async def setup_proxmox(hass, proxmox, config):
    """Create entities and load data from Proxmox VE."""
    conf = config.get(DOMAIN)
    conf_nodes = conf.get(CONF_NODES)
    conf_vms = conf.get(CONF_VMS)
    await update_data(hass, proxmox, conf_nodes, conf_vms)

    async def start(vm):
        """Start the VM or container"""
        vm_type = 'qemu'
        if 'type' in vm:
            vm_type = vm['type']
        uri = '{}/{}/{}/status/start'.format(vm['node'], vm_type, vm['vmid'])
        result = proxmox.nodes(uri).post()
        _LOGGER.info(result)
        fix_status(hass, vm, 'running')

    async def stop(vm):
        """Stop the VM or container"""
        vm_type = 'qemu'
        if 'type' in vm:
            vm_type = vm['type']
        uri = '{}/{}/{}/status/stop'.format(vm['node'], vm_type, vm['vmid'])
        result = proxmox.nodes(uri).post()
        _LOGGER.info(result)
        fix_status(hass, vm, 'stopped')

    hass.data[DATA_PROXMOX_CONTROL] = {'start': start, 'stop': stop}
    hass.async_create_task(
        discovery.async_load_platform(hass, 'sensor', DOMAIN, {}, config))
    hass.async_create_task(
        discovery.async_load_platform(hass, 'switch', DOMAIN, {}, config))
    hass.async_create_task(
        discovery.async_load_platform(
            hass, 'binary_sensor', DOMAIN, {}, config))

    async def async_update_proxmox(now):
        await update_data(hass, proxmox, conf_nodes, conf_vms)
        async_dispatcher_send(hass, SIGNAL_PROXMOX_UPDATED, None)

    async_track_time_interval(hass, async_update_proxmox, UPDATE_INTERVAL)


async def update_data(hass, proxmox, conf_nodes, conf_vms):
    """Update Proxmox VE data."""
    nodes = proxmox.nodes.get()
    node_dict = {}
    for node in nodes:
        name = node['node']
        if not bool(conf_nodes) or name in conf_nodes:
            node_dict[name] = node
            cts = proxmox.nodes(name).lxc.get()
            for ct in cts:
                if not bool(conf_vms) or int(ct['vmid']) in conf_vms:
                    ct['node'] = name
                    node_dict["{} - {}".format(ct['name'], ct['vmid'])] = ct
            vms = proxmox.nodes(name).qemu.get()
            for vm in vms:
                if not bool(conf_vms) or int(vm['vmid']) in conf_vms:
                    vm['node'] = name
                    node_dict["{} - {}".format(vm['name'], vm['vmid'])] = vm
    hass.data[DATA_PROXMOX_NODES] = node_dict


def fix_status(hass, vm, status):
    """Update the currently cached data with the new status of the vm
    in order to avoid the switch going back to the previous
    state until the cache is updated with the latest data.
    """
    data = hass.data[DATA_PROXMOX_NODES]
    vm['status'] = status
    data["{} - {}".format(vm['name'], vm['vmid'])] = vm
    hass.data[DATA_PROXMOX_NODES] = data
