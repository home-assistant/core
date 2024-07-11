"""Config flow for Tellduslive."""

import asyncio
import logging
import os

from tellduslive import Session, supports_local_api
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST
from homeassistant.util.json import load_json_object

from .const import (
    APPLICATION_NAME,
    CLOUD_NAME,
    DOMAIN,
    KEY_SCAN_INTERVAL,
    KEY_SESSION,
    NOT_SO_PRIVATE_KEY,
    PUBLIC_KEY,
    SCAN_INTERVAL,
    TELLDUS_CONFIG_FILE,
)

KEY_TOKEN = "token"
KEY_TOKEN_SECRET = "token_secret"

_LOGGER = logging.getLogger(__name__)


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Init config flow."""
        self._hosts = [CLOUD_NAME]
        self._host = None
        self._session = None
        self._scan_interval = SCAN_INTERVAL

    def _get_auth_url(self):
        self._session = Session(
            public_key=PUBLIC_KEY,
            private_key=NOT_SO_PRIVATE_KEY,
            host=self._host,
            application=APPLICATION_NAME,
        )
        return self._session.authorize_url

    async def async_step_user(self, user_input=None):
        """Let user select host or cloud."""
        if self._async_current_entries():
            return self.async_abort(reason="already_setup")

        if user_input is not None or len(self._hosts) == 1:
            if user_input is not None and user_input[CONF_HOST] != CLOUD_NAME:
                self._host = user_input[CONF_HOST]
            return await self.async_step_auth()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST): vol.In(list(self._hosts))}
            ),
        )

    async def async_step_auth(self, user_input=None):
        """Handle the submitted configuration."""
        errors = {}
        if user_input is not None:
            if await self.hass.async_add_executor_job(self._session.authorize):
                host = self._host or CLOUD_NAME
                if self._host:
                    session = {CONF_HOST: host, KEY_TOKEN: self._session.access_token}
                else:
                    session = {
                        KEY_TOKEN: self._session.access_token,
                        KEY_TOKEN_SECRET: self._session.access_token_secret,
                    }
                return self.async_create_entry(
                    title=host,
                    data={
                        CONF_HOST: host,
                        KEY_SCAN_INTERVAL: self._scan_interval.total_seconds(),
                        KEY_SESSION: session,
                    },
                )
            errors["base"] = "invalid_auth"

        try:
            async with asyncio.timeout(10):
                auth_url = await self.hass.async_add_executor_job(self._get_auth_url)
            if not auth_url:
                return self.async_abort(reason="unknown_authorize_url_generation")
        except TimeoutError:
            return self.async_abort(reason="authorize_url_timeout")
        except Exception:
            _LOGGER.exception("Unexpected error generating auth url")
            return self.async_abort(reason="unknown_authorize_url_generation")

        _LOGGER.debug("Got authorization URL %s", auth_url)
        return self.async_show_form(
            step_id="auth",
            errors=errors,
            description_placeholders={
                "app_name": APPLICATION_NAME,
                "auth_url": auth_url,
            },
        )

    async def async_step_discovery(self, discovery_info):
        """Run when a Tellstick is discovered."""
        await self._async_handle_discovery_without_unique_id()

        _LOGGER.info("Discovered tellstick device: %s", discovery_info)
        if supports_local_api(discovery_info[1]):
            _LOGGER.info("%s support local API", discovery_info[1])
            self._hosts.append(discovery_info[0])

        return await self.async_step_user()

    async def async_step_import(self, user_input):
        """Import a config entry."""
        if self._async_current_entries():
            return self.async_abort(reason="already_setup")

        self._scan_interval = user_input[KEY_SCAN_INTERVAL]
        if user_input[CONF_HOST] != DOMAIN:
            self._hosts.append(user_input[CONF_HOST])

        if not await self.hass.async_add_executor_job(
            os.path.isfile, self.hass.config.path(TELLDUS_CONFIG_FILE)
        ):
            return await self.async_step_user()

        conf = await self.hass.async_add_executor_job(
            load_json_object, self.hass.config.path(TELLDUS_CONFIG_FILE)
        )
        host = next(iter(conf))

        if user_input[CONF_HOST] != host:
            return await self.async_step_user()

        host = CLOUD_NAME if host == "tellduslive" else host
        return self.async_create_entry(
            title=host,
            data={
                CONF_HOST: host,
                KEY_SCAN_INTERVAL: self._scan_interval.total_seconds(),
                KEY_SESSION: next(iter(conf.values())),
            },
        )
