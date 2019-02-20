"""Config flow for Tellduslive."""
import asyncio
import logging
import os

import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.util.json import load_json

from .const import (
    APPLICATION_NAME, CLOUD_NAME, DOMAIN, KEY_HOST, KEY_SCAN_INTERVAL,
    KEY_SESSION, NOT_SO_PRIVATE_KEY, PUBLIC_KEY, SCAN_INTERVAL,
    TELLDUS_CONFIG_FILE)

KEY_TOKEN = 'token'
KEY_TOKEN_SECRET = 'token_secret'

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register('tellduslive')
class FlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Init config flow."""
        self._hosts = [CLOUD_NAME]
        self._host = None
        self._session = None
        self._scan_interval = SCAN_INTERVAL

    def _get_auth_url(self):
        return self._session.authorize_url

    async def async_step_user(self, user_input=None):
        """Let user select host or cloud."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason='already_setup')

        if user_input is not None or len(self._hosts) == 1:
            if user_input is not None and user_input[KEY_HOST] != CLOUD_NAME:
                self._host = user_input[KEY_HOST]
            return await self.async_step_auth()

        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema({
                vol.Required(KEY_HOST):
                vol.In(list(self._hosts))
            }))

    async def async_step_auth(self, user_input=None):
        """Handle the submitted configuration."""
        if not self._session:
            from tellduslive import Session
            self._session = Session(
                public_key=PUBLIC_KEY,
                private_key=NOT_SO_PRIVATE_KEY,
                host=self._host,
                application=APPLICATION_NAME,
            )

        if user_input is not None and self._session.authorize():
            host = self._host or CLOUD_NAME
            if self._host:
                session = {
                    KEY_HOST: host,
                    KEY_TOKEN: self._session.access_token
                }
            else:
                session = {
                    KEY_TOKEN: self._session.access_token,
                    KEY_TOKEN_SECRET: self._session.access_token_secret
                }
            return self.async_create_entry(
                title=host, data={
                    KEY_HOST: host,
                    KEY_SCAN_INTERVAL: self._scan_interval.seconds,
                    KEY_SESSION: session,
                })

        try:
            with async_timeout.timeout(10):
                auth_url = await self.hass.async_add_executor_job(
                    self._get_auth_url)
        except asyncio.TimeoutError:
            return self.async_abort(reason='authorize_url_timeout')
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error generating auth url")
            return self.async_abort(reason='authorize_url_fail')

        _LOGGER.debug('Got authorization URL %s', auth_url)
        return self.async_show_form(
            step_id='auth',
            description_placeholders={
                'app_name': APPLICATION_NAME,
                'auth_url': auth_url,
            },
        )

    async def async_step_discovery(self, user_input):
        """Run when a Tellstick is discovered."""
        from tellduslive import supports_local_api
        _LOGGER.info('Discovered tellstick device: %s', user_input)
        # Ignore any known devices
        for entry in self._async_current_entries():
            if entry.data[KEY_HOST] == user_input[0]:
                return self.async_abort(reason='already_configured')

        if not supports_local_api(user_input[1]):
            _LOGGER.debug('Tellstick does not support local API')
            # Configure the cloud service
            return await self.async_step_auth()

        self._hosts.append(user_input[0])
        return await self.async_step_user()

    async def async_step_import(self, user_input):
        """Import a config entry."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason='already_setup')

        self._scan_interval = user_input[KEY_SCAN_INTERVAL]
        if user_input[KEY_HOST] != DOMAIN:
            self._hosts.append(user_input[KEY_HOST])

        if not await self.hass.async_add_executor_job(
                os.path.isfile, self.hass.config.path(TELLDUS_CONFIG_FILE)):
            return await self.async_step_user()

        conf = await self.hass.async_add_executor_job(
            load_json, self.hass.config.path(TELLDUS_CONFIG_FILE))
        host = next(iter(conf))

        if user_input[KEY_HOST] != host:
            return await self.async_step_user()

        host = CLOUD_NAME if host == 'tellduslive' else host
        return self.async_create_entry(
            title=host,
            data={
                KEY_HOST: host,
                KEY_SCAN_INTERVAL: self._scan_interval.seconds,
                KEY_SESSION: next(iter(conf.values())),
            })
