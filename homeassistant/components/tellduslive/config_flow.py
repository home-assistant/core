"""Config flow for Tellduslive."""

import asyncio
from collections.abc import Mapping
import logging
from typing import Any, override

import probatio

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .api import Session, supports_local_api
from .const import (
    APPLICATION_NAME,
    CLOUD_NAME,
    DEFAULT_REQUEST_DELAY,
    DEFAULT_RETRY_INITIAL_DELAY,
    DEFAULT_RETRY_MAX_DELAY,
    DOMAIN,
    KEY_REQUEST_DELAY,
    KEY_RETRY_INITIAL_DELAY,
    KEY_RETRY_MAX_DELAY,
    KEY_SCAN_INTERVAL,
    KEY_SESSION,
    NOT_SO_PRIVATE_KEY,
    PUBLIC_KEY,
    SCAN_INTERVAL,
)

KEY_TOKEN = "token"
KEY_TOKEN_SECRET = "token_secret"

_LOGGER = logging.getLogger(__name__)


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    _session: Session

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return TelldusLiveOptionsFlow()

    def __init__(self) -> None:
        """Init config flow."""
        self._hosts = [CLOUD_NAME]
        self._host = None

    def _get_auth_url(self) -> str | None:
        self._session = Session(
            public_key=PUBLIC_KEY,
            private_key=NOT_SO_PRIVATE_KEY,
            host=self._host,
            application=APPLICATION_NAME,
        )
        return self._session.authorize_url

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let user select host or cloud."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None or len(self._hosts) == 1:
            if user_input is not None and user_input[CONF_HOST] != CLOUD_NAME:
                self._host = user_input[CONF_HOST]
            return await self.async_step_auth()

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_HOST): probatio.In(list(self._hosts))}
            ),
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data_updates={KEY_SESSION: session}
                    )
                return self.async_create_entry(
                    title=host,
                    data={
                        CONF_HOST: host,
                        KEY_SCAN_INTERVAL: SCAN_INTERVAL.total_seconds(),
                        KEY_SESSION: session,
                    },
                )
            errors["base"] = "invalid_auth"

        try:
            async with asyncio.timeout(10):
                auth_url = await self.hass.async_add_executor_job(self._get_auth_url)
        except TimeoutError:
            return self.async_abort(reason="authorize_url_timeout")
        except Exception:
            _LOGGER.exception("Unexpected error generating auth url")
            return self.async_abort(reason="unknown_authorize_url_generation")
        if not auth_url:
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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication against the host of the existing entry."""
        if entry_data[CONF_HOST] != CLOUD_NAME:
            self._host = entry_data[CONF_HOST]
        return await self.async_step_auth()

    @override
    async def async_step_discovery(
        self,
        discovery_info: list[str],  # type: ignore[override]
    ) -> ConfigFlowResult:
        """Run when a Tellstick is discovered."""
        await self._async_handle_discovery_without_unique_id()

        _LOGGER.debug("Discovered tellstick device: %s", discovery_info)
        if supports_local_api(discovery_info[1]):
            _LOGGER.debug("%s support local API", discovery_info[1])
            self._hosts.append(discovery_info[0])

        return await self.async_step_user()


def _seconds_selector(minimum: int, maximum: int) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=1,
            unit_of_measurement="s",
            mode=NumberSelectorMode.BOX,
        )
    )


class TelldusLiveOptionsFlow(OptionsFlow):
    """Handle the Telldus Live options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the polling and retry options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[KEY_RETRY_INITIAL_DELAY] > user_input[KEY_RETRY_MAX_DELAY]:
                errors["base"] = "retry_delay_order"
            else:
                return self.async_create_entry(
                    data={key: int(value) for key, value in user_input.items()}
                )

        options = self.config_entry.options
        defaults = {
            KEY_SCAN_INTERVAL: int(
                options.get(
                    KEY_SCAN_INTERVAL, self.config_entry.data[KEY_SCAN_INTERVAL]
                )
            ),
            KEY_RETRY_INITIAL_DELAY: options.get(
                KEY_RETRY_INITIAL_DELAY, DEFAULT_RETRY_INITIAL_DELAY
            ),
            KEY_RETRY_MAX_DELAY: options.get(
                KEY_RETRY_MAX_DELAY, DEFAULT_RETRY_MAX_DELAY
            ),
            KEY_REQUEST_DELAY: options.get(KEY_REQUEST_DELAY, DEFAULT_REQUEST_DELAY),
        }
        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(KEY_SCAN_INTERVAL): _seconds_selector(
                            30, 3600
                        ),
                        probatio.Required(KEY_RETRY_INITIAL_DELAY): _seconds_selector(
                            5, 3600
                        ),
                        probatio.Required(KEY_RETRY_MAX_DELAY): _seconds_selector(
                            5, 86400
                        ),
                        probatio.Required(KEY_REQUEST_DELAY): _seconds_selector(0, 60),
                    }
                ),
                user_input or defaults,
            ),
        )
