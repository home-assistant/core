"""
Support for Molohub.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/molohub/
"""

from homeassistant.const import (EVENT_HOMEASSISTANT_START,
                                 EVENT_HOMEASSISTANT_STOP, EVENT_STATE_CHANGED)

from .molo_client_config import MOLO_CONFIGS
from .notify_state import NOTIFY_STATE
from .utils import LOGGER

DOMAIN = 'molohub'
NOTIFYID = 'molouhubnotifyid'


def setup(hass, config):
    """Set up molohub component."""
    LOGGER.info("Begin setup molohub!")

    # Load config mode from configuration.yaml.
    cfg = config[DOMAIN]
    if 'mode' in cfg:
        MOLO_CONFIGS.load(cfg['mode'])
    else:
        MOLO_CONFIGS.load('release')
    tmp_haweb = MOLO_CONFIGS.get_config_object()['server']['haweb']
    NOTIFY_STATE.set_context(hass, tmp_haweb)

    if 'http' in config and 'server_host' in config['http']:
        tmp_host = config['http']['server_host']
        MOLO_CONFIGS.get_config_object()['ha']['host'] = tmp_host
    if 'http' in config and 'server_port' in config['http']:
        tmp_port = config['http']['server_port']
        MOLO_CONFIGS.get_config_object()['ha']['port'] = tmp_port

    def send_notify(notify_str):
        """Update UI."""
        global NOTIFYID
        LOGGER.debug("Send notify: %s", notify_str)
        hass.components.persistent_notification.async_create(
            notify_str, "Molo Hub Infomation", NOTIFYID)

    async def stop_molohub(event):
        """Stop Molohub while closing ha."""
        LOGGER.info("Begin stop molohub!")
        from .molo_hub_main import stop_proxy
        stop_proxy()

    async def start_molohub(event):
        """Start Molohub while starting ha."""
        LOGGER.debug("molohub started!")
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_molohub)

    async def handle_event(event):
        """Handle Molohub event."""
        send_notify(NOTIFY_STATE.get_notify_str())

    async def on_state_changed(event):
        """Disable the dismiss button."""
        global NOTIFYID
        state = event.data.get('new_state')
        entity_id = event.data.get('entity_id')
        if not state and entity_id and entity_id.find(NOTIFYID) != -1:
            send_notify(NOTIFY_STATE.get_notify_str())

    from .molo_hub_main import run_proxy
    run_proxy(hass)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_molohub)
    hass.bus.async_listen(EVENT_STATE_CHANGED, on_state_changed)
    hass.bus.async_listen('molohub_event', handle_event)
    send_notify(NOTIFY_STATE.get_notify_str())

    return True
