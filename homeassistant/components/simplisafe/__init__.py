"""
Support for SimpliSafe alarm systems.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/simplisafe/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_CODE, CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_TOKEN, CONF_USERNAME)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from homeassistant.helpers import config_validation as cv

from .config_flow import configured_instances
from .const import DATA_CLIENT, DEFAULT_SCAN_INTERVAL, DOMAIN, TOPIC_UPDATE

REQUIREMENTS = ['simplisafe-python==3.1.14']

_LOGGER = logging.getLogger(__name__)

CONF_ACCOUNTS = 'accounts'

DATA_LISTENER = 'listener'

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


@callback
def _async_save_refresh_token(hass, config_entry, token):
    hass.config_entries.async_update_entry(
        config_entry, data={
            **config_entry.data, CONF_TOKEN: token
        })


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

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={'source': SOURCE_IMPORT},
                data={
                    CONF_USERNAME: account[CONF_USERNAME],
                    CONF_PASSWORD: account[CONF_PASSWORD],
                    CONF_CODE: account.get(CONF_CODE),
                    CONF_SCAN_INTERVAL: account[CONF_SCAN_INTERVAL],
                }))

    return True


async def async_setup_entry(hass, config_entry):
    """Set up SimpliSafe as config entry."""
    from simplipy import API
    from simplipy.errors import InvalidCredentialsError, SimplipyError

    websession = aiohttp_client.async_get_clientsession(hass)

    try:
        simplisafe = await API.login_via_token(
            config_entry.data[CONF_TOKEN], websession)
    except InvalidCredentialsError:
        _LOGGER.error('Invalid credentials provided')
        return False
    except SimplipyError as err:
        _LOGGER.error('Config entry failed: %s', err)
        raise ConfigEntryNotReady

    _async_save_refresh_token(hass, config_entry, simplisafe.refresh_token)

    systems = await simplisafe.get_systems()
    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = systems

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(
            config_entry, 'alarm_control_panel'))

    async def refresh(event_time):
        """Refresh data from the SimpliSafe account."""
        for system in systems:
            _LOGGER.debug('Updating system data: %s', system.system_id)
            await system.update()
            async_dispatcher_send(hass, TOPIC_UPDATE.format(system.system_id))

            if system.api.refresh_token_dirty:
                _async_save_refresh_token(
                    hass, config_entry, system.api.refresh_token)

    hass.data[DOMAIN][DATA_LISTENER][
        config_entry.entry_id] = async_track_time_interval(
            hass,
            refresh,
            timedelta(seconds=config_entry.data[CONF_SCAN_INTERVAL]))

    return True


async def async_unload_entry(hass, entry):
    """Unload a SimpliSafe config entry."""
    await hass.config_entries.async_forward_entry_unload(
        entry, 'alarm_control_panel')

    hass.data[DOMAIN][DATA_CLIENT].pop(entry.entry_id)
    remove_listener = hass.data[DOMAIN][DATA_LISTENER].pop(entry.entry_id)
    remove_listener()

    return True
