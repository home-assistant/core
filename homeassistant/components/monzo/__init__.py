"""
Support for Monzo accounts.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/monzo/
"""
from datetime import timedelta
import logging
import time

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, CONF_SCAN_INTERVAL, CONF_SENSORS)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .config_flow import configured_instances
from .const import (
    DOMAIN, CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN, CONF_LAST_SAVED_AT, CONF_EXPIRES_AT)

REQUIREMENTS = ['monzo==0.8.0']

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)


DATA_MONZO_CLIENT = 'data_client'
DATA_MONZO_LISTENER = 'data_listener'
DATA_MONZO_CONFIG = 'monzo_config'
DATA_BALANCE = 'balance'
DATA_POTS = 'pots'
DATA_ACCOUNTID = 'account_id'

DEFAULT_ATTRIBUTION = 'Data provided by Monzo'
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)

TOPIC_UPDATE = '{0}_data_update'.format(DOMAIN)

TYPE_BALANCE = 'balance'
TYPE_DAILY_SPEND = 'dailyspend'
TYPE_POTS = 'pots'

SENSORS = {
    TYPE_BALANCE: ['Account Balance', 'mdi:cash', 'GBP'],
    TYPE_DAILY_SPEND: ['Spent Today', 'mdi:cash', 'GBP'],
    TYPE_POTS: ['Balance', 'mdi:cash', 'GBP']
}

SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSORS)):
        vol.All(cv.ensure_list, [vol.In(SENSORS)])
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Optional(CONF_SENSORS): SENSOR_SCHEMA,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL):
            cv.time_period,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up Monzo components."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_MONZO_CLIENT] = {}
    hass.data[DOMAIN][DATA_MONZO_LISTENER] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    client_id = conf.get(CONF_CLIENT_ID)
    client_secret = conf.get(CONF_CLIENT_SECRET)

    hass.async_add_job(hass.config_entries.flow.async_init(
        DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
        data={
            CONF_CLIENT_ID: client_id,
            CONF_CLIENT_SECRET: client_secret
        }
    ))

    # Store config to be used during entry setup
    hass.data[DATA_MONZO_CONFIG] = conf

    return True


async def async_setup_entry(hass, config_entry):
    """Set up Monzo as a config entry."""
    # Get sensors as defined in configuration.yaml
    sensors = hass.data.get(DATA_MONZO_CONFIG, {}).get(CONF_SENSORS, {}).get(
        CONF_MONITORED_CONDITIONS, list(SENSORS))

    monzo = MonzoObject(hass, sensors, config_entry)
    await monzo.async_update()

    # Make Monzo client available
    hass.data[DOMAIN][DATA_MONZO_CLIENT][config_entry.entry_id] = monzo

    _LOGGER.debug("proceeding with setup")

    # Create config entries for each component.
    for component in ('sensor',):
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(
            config_entry, component))

    async def refresh_sensors(event_time):
        """Refresh Monzo data."""
        _LOGGER.debug('Refreshing Monzo data')
        await monzo.async_update()
        async_dispatcher_send(hass, TOPIC_UPDATE)

    # Automatically poll Monzo on set interval and update stored data
    hass.data[DOMAIN][DATA_MONZO_LISTENER][
        config_entry.entry_id] = async_track_time_interval(
            hass, refresh_sensors,
            hass.data.get(DATA_MONZO_CONFIG, {}).get(CONF_SCAN_INTERVAL,
                                                     DEFAULT_SCAN_INTERVAL))

    _LOGGER.debug("async_setup_monzo is done")

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a Monzo config entry."""
    for component in ('sensor',):
        await hass.config_entries.async_forward_entry_unload(
            config_entry, component)

    hass.data[DOMAIN][DATA_MONZO_CLIENT].pop(config_entry.entry_id)

    remove_listener = hass.data[DOMAIN][DATA_MONZO_LISTENER].pop(
        config_entry.entry_id)
    remove_listener()

    return True


class MonzoObject:
    """Define a generic Monzo object."""

    def __init__(self, hass, sensor_conditions, config_entry):
        """Initialize."""
        from monzo.monzo import Monzo
        from monzo.auth import MonzoOAuth2Client

        self.data = {}
        self._hass = hass
        self.sensor_conditions = sensor_conditions
        self.config_entry = config_entry

        client_id = config_entry.data['tokens'][CONF_CLIENT_ID]
        client_secret = config_entry.data['tokens'][CONF_CLIENT_SECRET]
        access_token = config_entry.data['tokens'][CONF_ACCESS_TOKEN]
        refresh_token = config_entry.data['tokens'][CONF_REFRESH_TOKEN]
        last_saved_at = config_entry.data['tokens'].get(CONF_LAST_SAVED_AT)
        expires_at = config_entry.data['tokens'].get(CONF_EXPIRES_AT,
                                                     last_saved_at)

        oauth_client = MonzoOAuth2Client(
            client_id=client_id,
            client_secret=client_secret,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            refresh_callback=self.update_config_entry)

        self.client = Monzo.from_oauth_session(oauth_client)

    async def async_update(self):
        """Update sensor data."""
        if any(sensor_type in self.sensor_conditions for
               sensor_type in (TYPE_BALANCE, TYPE_DAILY_SPEND)):
            account = await self._hass.async_add_executor_job(
                self.client.get_first_account)

            account_id = account['id']
            self.data[DATA_ACCOUNTID] = account_id

            balance = await self._hass.async_add_executor_job(
                self.client.get_balance, account_id)

            self.data[DATA_BALANCE] = balance

        if TYPE_POTS in self.sensor_conditions:
            all_pots = await self._hass.async_add_executor_job(
                self.client.get_pots)

            open_pots = [pot for pot in all_pots['pots'] if not pot['deleted']]
            self.data[DATA_POTS] = open_pots

    @callback
    def update_config_entry(self, new_token):
        """Update config entry with refreshed token."""
        new_data = {**self.config_entry.data,
                    'tokens': new_token,
                    CONF_LAST_SAVED_AT: int(time.time())}
        self._hass.config_entries.async_update_entry(self.config_entry,
                                                     data=new_data)
