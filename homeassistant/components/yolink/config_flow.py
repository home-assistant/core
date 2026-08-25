"""Config flow for yolink."""

import asyncio
from collections.abc import Mapping
import logging
from typing import Any, override

import voluptuous as vol
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
    """Return the general information of the home the credentials belong to.

    Only the home information is requested, so unlike YoLinkHome.async_setup
    this neither loads the devices nor opens an MQTT connection.
    """
    async with asyncio.timeout(10):
        home_info = await YoLinkClient(auth_mgr).execute(
            url=Endpoints.US.value.url, bsdp={"method": "Home.getGeneralInfo"}
        )
    if not isinstance(home_info.data, dict):
        # The data of a response is optional: an accepted request that answered
        # without any is as unusable as a refused one.
        raise YoLinkClientError(
            "invalid_response", "Response carries no home information"
        )
    return home_info.data


UAC_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_UAID): selector.TextSelector(),
        vol.Required(CONF_SECRET_KEY): selector.TextSelector(
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
                home_id = home_info.get("id")
                if not home_id:
                    errors["base"] = "unknown"
                else:
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
                    if self._async_home_id_configured(home_id):
                        # The home is managed by the OAuth2 entry, whose unique
                        # id is the domain rather than the home id.
                        return self.async_abort(reason="already_configured")

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
        data[CONF_AUTH_TYPE] = AUTH_TYPE_OAUTH

        if self.source == SOURCE_REAUTH:
            return await self._async_reauth_oauth_entry(data)

        # Entries created before UAC support use the domain as unique id, which
        # limits OAuth2 to a single entry.
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        try:
            home_id = await self._async_lookup_home_id(data["token"]["access_token"])
        except YoLinkAuthFailError:
            return self.async_abort(reason="oauth_unauthorized")

        if home_id:
            if self._async_home_id_configured(home_id):
                return self.async_abort(reason="already_configured")
            data[CONF_HOME_ID] = home_id
        elif self._async_other_entry_configured():
            # Only UAC entries can be left here, and any of them may manage the
            # home of this account. An unknown home cannot be told apart from
            # theirs, so setup would record it on two entries instead of the
            # flow refusing the duplicate.
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(title="YoLink", data=data)

    async def _async_reauth_oauth_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Update the reauthenticated entry with the token that was resolved."""
        reauth_entry = self._get_reauth_entry()

        try:
            home_id = await self._async_lookup_home_id(data["token"]["access_token"])
        except YoLinkAuthFailError:
            return self.async_abort(reason="oauth_unauthorized")

        if not home_id:
            if self._async_other_entry_configured(
                ignore_entry_id=reauth_entry.entry_id
            ):
                # As in async_oauth_create_entry: the home another entry manages
                # cannot be ruled out without the home id, so the token is left
                # unwritten rather than bypassing the duplicate check.
                return self.async_abort(reason="cannot_connect")
            # The account may have changed, so the recorded home id can no
            # longer be trusted. Dropping it lets setup record the home again,
            # which a merge of data updates could not do.
            entry_data = {**reauth_entry.data, **data}
            entry_data.pop(CONF_HOME_ID, None)
            return self.async_update_reload_and_abort(reauth_entry, data=entry_data)

        if self._async_home_id_configured(
            home_id, ignore_entry_id=reauth_entry.entry_id
        ):
            return self.async_abort(reason="already_configured")

        return self.async_update_reload_and_abort(
            reauth_entry, data_updates={**data, CONF_HOME_ID: home_id}
        )

    async def _async_lookup_home_id(self, access_token: str) -> str | None:
        """Return the id of the home the account owns, or None if unknown.

        Recording the home is a best effort enhancement of an account the API
        already accepted, so every failure other than a refused token leaves the
        home unknown instead of ending the flow.
        """
        try:
            home_info = await _async_fetch_home_info(
                StaticTokenAuth(
                    aiohttp_client.async_get_clientsession(self.hass), access_token
                )
            )
        except YoLinkAuthFailError:
            raise
        except Exception as err:  # noqa: BLE001
            # Deliberately broad: an unreachable API, a malformed response and a
            # bug in the lookup all cost no more than the home id, and none of
            # them may keep an authorized account from being set up.
            _LOGGER.debug("Could not determine the home of the account: %s", err)
            return None
        return home_info.get("id")

    def _async_home_id_configured(
        self, home_id: str, ignore_entry_id: str | None = None
    ) -> bool:
        """Return if an entry other than ignore_entry_id manages the home."""
        return any(
            entry.data.get(CONF_HOME_ID) == home_id
            for entry in self._async_current_entries()
            if entry.entry_id != ignore_entry_id
        )

    def _async_other_entry_configured(self, ignore_entry_id: str | None = None) -> bool:
        """Return if an entry other than ignore_entry_id is configured."""
        return any(
            entry.entry_id != ignore_entry_id for entry in self._async_current_entries()
        )

    def _async_oauth_entry_exists(self) -> bool:
        """Return if an OAuth2 based entry is already configured."""
        return any(
            # Entries created before UAC support was added have no auth type.
            entry.data.get(CONF_AUTH_TYPE, AUTH_TYPE_OAUTH) == AUTH_TYPE_OAUTH
            for entry in self._async_current_entries()
        )
