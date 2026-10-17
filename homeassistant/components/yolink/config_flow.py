"""Config flow for yolink."""

import asyncio
from collections.abc import Mapping
import logging
from typing import Any, override

import probatio
from yolink.auth_mgr import YoLinkAuthMgr
from yolink.client import YoLinkClient
from yolink.endpoint import Endpoints
from yolink.exception import YoLinkAuthFailError, YoLinkClientError

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow, selector

from .api import StaticTokenAuth, UACAuth
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


async def _async_fetch_home_info(auth_mgr: YoLinkAuthMgr) -> dict[str, Any]:
    """Return the general information of the home, without loading its devices."""
    async with asyncio.timeout(10):
        response = await YoLinkClient(auth_mgr).execute(
            url=Endpoints.US.value.url, bsdp={"method": "Home.getGeneralInfo"}
        )
    if not isinstance(response.data, dict) or not response.data.get("id"):
        raise YoLinkClientError("invalid_response", "Response carries no home id")
    return response.data


UAC_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_UAID): selector.TextSelector(),
        probatio.Required(probatio.Secret(CONF_SECRET_KEY)): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle yolink OAuth2 and UAC authentication."""

    DOMAIN = DOMAIN

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    @override
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": "create"}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        if self._async_oauth_entry_exists():
            # Only one OAuth2 entry is supported, so UAC is the only way left
            # to add another home.
            return await self.async_step_uac()

        return self.async_show_menu(
            step_id="user",
            menu_options=["pick_implementation", "uac"],
        )

    @override
    async def async_step_pick_implementation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle selection of an OAuth2 implementation."""
        # Reauthenticating the existing OAuth2 entry must remain possible.
        if self.source != SOURCE_REAUTH and self._async_oauth_entry_exists():
            return self.async_abort(reason="already_configured")

        return await super().async_step_pick_implementation(user_input)

    async def async_step_uac(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle UAC credential input."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                home_info = await _async_fetch_home_info(
                    UACAuth(
                        aiohttp_client.async_get_clientsession(self.hass),
                        user_input[CONF_UAID],
                        user_input[CONF_SECRET_KEY],
                    )
                )
            except YoLinkAuthFailError:
                errors["base"] = "invalid_auth"
            except YoLinkClientError, TimeoutError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during UAC validation")
                errors["base"] = "unknown"
            else:
                home_id = home_info["id"]
                # Keying on the home id allows one entry per home instead
                # of one per account.
                await self.async_set_unique_id(home_id)

                if self.source == SOURCE_REAUTH:
                    self._abort_if_unique_id_mismatch(reason="wrong_account")
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(),
                        data_updates={
                            CONF_UAID: user_input[CONF_UAID],
                            CONF_SECRET_KEY: user_input[CONF_SECRET_KEY],
                            CONF_HOME_ID: home_id,
                        },
                    )

                self._abort_if_unique_id_configured()
                self._async_abort_entries_match({CONF_HOME_ID: home_id})

                return self.async_create_entry(
                    title=home_info.get("name", "YoLink Home"),
                    data={
                        CONF_AUTH_TYPE: AUTH_TYPE_UAC,
                        CONF_UAID: user_input[CONF_UAID],
                        CONF_SECRET_KEY: user_input[CONF_SECRET_KEY],
                        CONF_HOME_ID: home_id,
                    },
                )

        return self.async_show_form(
            step_id="uac",
            data_schema=UAC_SCHEMA,
            errors=errors,
        )

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

        if self._get_reauth_entry().data.get(CONF_AUTH_TYPE) == AUTH_TYPE_UAC:
            return await self.async_step_uac()

        return await super().async_step_user()

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        if self.source != SOURCE_REAUTH:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

        try:
            home_info = await _async_fetch_home_info(
                StaticTokenAuth(
                    aiohttp_client.async_get_clientsession(self.hass),
                    data["token"]["access_token"],
                )
            )
        except YoLinkAuthFailError:
            return self.async_abort(reason="oauth_unauthorized")
        except YoLinkClientError, TimeoutError:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected exception during home lookup")
            return self.async_abort(reason="unknown")

        home_id = home_info["id"]
        self._async_abort_entries_match({CONF_HOME_ID: home_id})
        data |= {CONF_AUTH_TYPE: AUTH_TYPE_OAUTH, CONF_HOME_ID: home_id}

        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=data
            )
        return self.async_create_entry(title="YoLink", data=data)

    def _async_oauth_entry_exists(self) -> bool:
        """Return if an OAuth2 based entry is already configured."""
        return any(
            # Entries created before UAC support was added have no auth type.
            entry.data.get(CONF_AUTH_TYPE, AUTH_TYPE_OAUTH) == AUTH_TYPE_OAUTH
            for entry in self._async_current_entries()
        )
