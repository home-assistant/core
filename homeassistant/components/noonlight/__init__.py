"""Noonlight platform for HomeAssistant"""
from datetime import datetime, timedelta
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_ACCESS_TOKEN, CONF_BINARY_SENSORS, CONF_FILENAME, CONF_ID,
    CONF_LATITUDE, CONF_LONGITUDE, CONF_MONITORED_CONDITIONS, CONF_SENSORS,
    CONF_STRUCTURE, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.event import async_track_point_in_utc_time
import homeassistant.util.dt as dt_util

DOMAIN = 'noonlight'

TOKEN_CHECK_INTERVAL = timedelta(minutes=15)

CONF_SECRET = 'secret'
CONF_API_ENDPOINT = 'api_endpoint'
CONF_TOKEN_ENDPOINT = 'token_endpoint'
    
REQUIREMENTS = ['noonlight>=0.1.0']

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_ID): cv.string,
        vol.Required(CONF_SECRET): cv.string,
        vol.Required(CONF_API_ENDPOINT): cv.string,
        vol.Required(CONF_TOKEN_ENDPOINT): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    if DOMAIN not in config:
        return True
        
    conf = config[DOMAIN]
        
    
    if DOMAIN not in hass.data:
        noonlight_platform = NoonlightPlatform(hass, conf)
        hass.data[DOMAIN] = noonlight_platform

    async def check_api_token(now):
        """Check if the current API token has expired and renew if so"""
        
        next_check_interval = TOKEN_CHECK_INTERVAL
        
        result = await noonlight_platform.check_api_token()
        
        if not result:
            _LOGGER.error("api token failed renewal, retrying in 3 min...")
            next_check_interval = timedelta(minutes=3)

        async_track_point_in_utc_time(
            hass, check_api_token, dt_util.utcnow() + next_check_interval)

    @callback
    def schedule_first_token_check(event):
        """Schedule the first token renewal when Home Assistant starts up."""
        async_track_point_in_utc_time(hass, check_api_token, dt_util.utcnow())

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, 
        schedule_first_token_check)
    
    load_platform(hass, 'switch', DOMAIN, None, config)
    
    return True
    
class NoonlightPlatform(object):
    """Platform for interacting with Noonlight from HomeAssistant"""
    def __init__(self, hass, conf):
        self.hass = hass
        self.config = conf
        self._client = None
        self._time_to_renew = timedelta(hours=2)
        
    @property
    def latitude(self):
        return self.config \
            .get(CONF_LATITUDE, self.hass.config.latitude)
        
    @property
    def longitude(self):
        return self.config \
            .get(CONF_LONGITUDE, self.hass.config.longitude)
        
    @property
    def access_token(self):
        return self.config \
            .get(CONF_ACCESS_TOKEN,{}) \
            .get('token')
        
    @property
    def access_token_expiry(self):
        return self.config \
            .get(CONF_ACCESS_TOKEN,{}) \
            .get('expires',dt_util.utc_from_timestamp(0))
        
    @property
    def access_token_expires_in(self):
        return self.access_token_expiry - dt_util.utcnow()
        
    @property
    def should_token_be_renewed(self):
        return self.access_token is None \
            or self.access_token_expires_in <= self._time_to_renew
        
    @property
    def client(self):
        if self._client is None:
            import noonlight as nl
            self._client = nl.NoonlightClient(token = self.access_token)
        return self._client
        
    async def check_api_token(self, force_renew = False):
        _LOGGER.debug("checking if token needs renewal, expires: {0:.1f}h" \
            .format(self.access_token_expires_in.total_seconds() / 3600.0))
        if self.should_token_be_renewed or force_renew:
            try:
                _LOGGER.debug("Renewing Noonlight access token...")
                path = self.config.get(CONF_TOKEN_ENDPOINT)
                data = {
                    'id': self.config.get(CONF_ID), 
                    'secret': self.config.get(CONF_SECRET)
                }
                token_response = await self.client._post(path=path, data=data)
                if 'token' in token_response and 'expires' in token_response:
                    self._set_token_response(token_response)
                    _LOGGER.debug("token renewed, expires at {0} ({1:.1f}h)" \
                        .format(
                            self.access_token_expiry,
                            self.access_token_expires_in.total_seconds()/3600.0
                        )
                    )
                    return True
                else:
                    raise Exception("unexpected token_response: {}" \
                        .format(token_response))
            except:
                _LOGGER.exception("Failed to renew Noonlight token!")
                return False
        return True
                
    def _set_token_response(self, token_response):
        expires = dt_util.parse_datetime(token_response['expires'])
        if expires is not None:
            token_response['expires'] = expires
        else:
            token_response['expires'] = dt_util.utc_from_timestamp(0)
        self.client.set_token(token = token_response.get('token'))
        self.config[CONF_ACCESS_TOKEN] = token_response
