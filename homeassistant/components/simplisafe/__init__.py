"""
Support for SimpliSafe alarm systems.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/simplisafe/
"""
import logging

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    SCAN_INTERVAL as DEFAULT_SCAN_INTERVAL)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_CODE, CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME)
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.json import load_json, save_json

from homeassistant.helpers import config_validation as cv

from .config_flow import configured_instances
from .const import (
    DATA_CLIENT, DATA_FILE_SCAFFOLD, DATA_LISTENER, DOMAIN, TOPIC_UPDATE)

CONF_TOKEN_FILE = 'token_file'


REQUIREMENTS = ['simplisafe-python==3.1.3']

_LOGGER = logging.getLogger(__name__)

CONF_ACCOUNTS = 'accounts'

ACCOUNT_CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_CODE): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL):
        cv.time_period
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_ACCOUNTS):
            vol.All(cv.ensure_list, [ACCOUNT_CONFIG_SCHEMA]),
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the SimpliSafe component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CLIENT] = {}
    hass.data[DOMAIN][DATA_LISTENER] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    for account in conf[CONF_ACCOUNTS]:
        if account[CONF_USERNAME] in configured_instances(hass):
            continue

        hass.async_add_job(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={'source': SOURCE_IMPORT},
                data={
                    CONF_USERNAME: account[CONF_USERNAME],
                    CONF_PASSWORD: account[CONF_PASSWORD],
                    CONF_CODE: account.get(CONF_CODE),
                }))

    return True


async def async_setup_entry(hass, config_entry):
    """Set up OpenUV as config entry."""
    from simplipy import API
    from simplipy.errors import SimplipyError

    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    token_filepath = hass.config.path(DATA_FILE_SCAFFOLD.format(username))
    token_data = await hass.async_add_executor_job(
        load_json, token_filepath)

    websession = aiohttp_client.async_get_clientsession(hass)

    try:
        if token_data:
            try:
                simplisafe = await API.login_via_token(
                    token_data['refresh_token'], websession)
                _LOGGER.debug('Logging in with refresh token')
            except SimplipyError:
                _LOGGER.info('Refresh token expired; using credentials')
                simplisafe = await API.login_via_credentials(
                    username, password, websession)
        else:
            simplisafe = await API.login_via_credentials(
                username, password, websession)
            _LOGGER.debug('Logging in with credentials')
    except SimplipyError as err:
        _LOGGER.error("There was an error during setup: %s", err)
        return

    systems = await simplisafe.get_systems()
    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = systems

    token_data = {'refresh_token': simplisafe.refresh_token}
    await hass.async_add_executor_job(
        save_json, token_filepath, token_data)

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(
            config_entry, 'alarm_control_panel'))

    async def refresh(event_time):
        """Refresh data from the SimpliSafe account."""
        for system in systems:
            _LOGGER.debug('Updating system data: %s', system.system_id)
            await system.update()
            async_dispatcher_send(hass, TOPIC_UPDATE.format(system.system_id))

    hass.data[DOMAIN][DATA_LISTENER][
        config_entry.entry_id] = async_track_time_interval(
            hass, refresh,
            config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

    return True


async def async_unload_entry(hass, entry):
    """Unload a SimpliSafe config entry."""
    hass.data[DOMAIN][DATA_CLIENT].pop(entry.entry_id)
    remove_listener = hass.data[DOMAIN][DATA_LISTENER].pop(entry.entry_id)
    remove_listener()

    return True
