"""Config flow for yolink."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol
from yolink.device import YoLinkDevice
from yolink.exception import YoLinkAuthFailError, YoLinkClientError
from yolink.home_manager import YoLinkHome
from yolink.message_listener import MessageListener

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from .api import UACAuth
from .const import (
    AUTH_TYPE_OAUTH,
    AUTH_TYPE_UAC,
    CONF_AUTH_TYPE,
    CONF_HOME_ID,
    CONF_SECRET_KEY,
    CONF_UAID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class _NoOpMessageListener(MessageListener):
    """No-op message listener for config flow validation."""

    def on_message(self, device: YoLinkDevice, msg_data: dict[str, Any]) -> None:
        """Do nothing with messages during validation."""


UAC_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_UAID): str,
        vol.Required(CONF_SECRET_KEY): str,
    }
)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle yolink OAuth2 and UAC authentication."""

    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._home_id: str | None = None
        self._home_name: str | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": "create"}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start - show menu to choose auth method."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["pick_implementation", "uac"],
        )

    async def async_step_uac(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle UAC credential input."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                home_info = await self._async_validate_uac_credentials(
                    user_input[CONF_UAID],
                    user_input[CONF_SECRET_KEY],
                )
            except YoLinkAuthFailError as err:
                _LOGGER.error("UAC auth failed: %s", err)
                errors["base"] = "invalid_auth"
            except YoLinkClientError as err:
                _LOGGER.error("UAC client error: %s", err)
                errors["base"] = "cannot_connect"
            except TimeoutError:
                _LOGGER.error("UAC validation timed out")
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during UAC validation")
                errors["base"] = "unknown"
            else:
                self._home_id = home_info["id"]
                self._home_name = home_info.get("name", "YoLink Home")

                # Use home_id as unique identifier to allow multiple homes
                await self.async_set_unique_id(self._home_id)

                if self.source == SOURCE_REAUTH:
                    self._abort_if_unique_id_mismatch(reason="wrong_account")
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(),
                        data_updates={
                            CONF_AUTH_TYPE: AUTH_TYPE_UAC,
                            CONF_UAID: user_input[CONF_UAID],
                            CONF_SECRET_KEY: user_input[CONF_SECRET_KEY],
                            CONF_HOME_ID: self._home_id,
                        },
                    )

                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=self._home_name,
                    data={
                        CONF_AUTH_TYPE: AUTH_TYPE_UAC,
                        CONF_UAID: user_input[CONF_UAID],
                        CONF_SECRET_KEY: user_input[CONF_SECRET_KEY],
                        CONF_HOME_ID: self._home_id,
                    },
                )

        return self.async_show_form(
            step_id="uac",
            data_schema=UAC_SCHEMA,
            errors=errors,
        )

    async def _async_validate_uac_credentials(
        self, uaid: str, secret_key: str
    ) -> dict[str, Any]:
        """Validate UAC credentials and return home info."""
        websession = aiohttp_client.async_get_clientsession(self.hass)
        auth_mgr = UACAuth(self.hass, websession, uaid, secret_key)

        yolink_home = YoLinkHome()
        async with asyncio.timeout(10):
            # Use no-op listener for validation
            await yolink_home.async_setup(auth_mgr, _NoOpMessageListener())
            home_info = await yolink_home.async_get_home_info()
            await yolink_home.async_unload()

        _LOGGER.debug(
            "Validated UAC credentials for home: id=%s, name=%s",
            home_info.data.get("id"),
            home_info.data.get("name"),
        )
        return home_info.data

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")

        # Check auth type of existing entry and route appropriately
        reauth_entry = self._get_reauth_entry()
        if reauth_entry.data.get(CONF_AUTH_TYPE) == AUTH_TYPE_UAC:
            return await self.async_step_uac()
        # For OAuth, use the standard OAuth flow (call without user_input to start fresh)
        return await super().async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data_updates={**data, CONF_AUTH_TYPE: AUTH_TYPE_OAUTH},
            )

        # For OAuth entries, use DOMAIN as unique_id (backwards compatible)
        # This limits OAuth to one entry, but UAC entries are unlimited
        existing_entry = await self.async_set_unique_id(DOMAIN)
        if existing_entry:
            return self.async_abort(reason="already_configured")

        data[CONF_AUTH_TYPE] = AUTH_TYPE_OAUTH
        return self.async_create_entry(title="YoLink", data=data)
