"""Config flow to configure SmartThings."""

from collections.abc import Mapping
import logging
from typing import Any, override
from uuid import uuid4

import probatio
from pysmartthings import (
    SmartThings,
    SmartThingsAuthenticationFailedError,
    SmartThingsConnectionError,
    SmartThingsForbiddenError,
    SmartThingsQuotaExceededError,
)

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2FlowHandler,
    AbstractOAuth2Implementation,
    ImplementationUnavailableError,
    async_get_config_entry_implementation,
    async_get_implementations,
    async_get_redirect_uri,
)
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import dt as dt_util

from .app_ledger import async_get_app_ledger
from .const import (
    APP_NAME_PREFIX,
    CONF_APP_ID,
    CONF_LOCATION_ID,
    CONF_PAT_TOKEN,
    DOMAIN,
    HOME_ASSISTANT_CLOUD_CLIENT_ID,
    MANAGE_PLANS_URL,
    OLD_DATA,
    PAT_IMPLEMENTATION,
    PAT_TOKEN_URL,
    REQUESTED_SCOPES,
    SCOPES,
    app_auth_domain,
)

_LOGGER = logging.getLogger(__name__)


class SmartThingsConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle configuration of SmartThings integrations."""

    VERSION = 3
    MINOR_VERSION = 3
    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._app_id: str | None = None
        self._implementations: dict[str, AbstractOAuth2Implementation] = {}

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    @override
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": " ".join(REQUESTED_SCOPES)}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Check how we should authenticate with SmartThings."""
        return await self.async_step_pick_implementation(user_input)

    @override
    async def async_step_pick_implementation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick between Home Assistant Cloud or a personal access token.

        Overrides the base class: any stored application-credential
        implementations are surfaced one level down, under the "Personal
        access token" choice, instead of being flattened into this list.
        """
        try:
            self._implementations = await async_get_implementations(self.hass, DOMAIN)
        except ImplementationUnavailableError:
            self._implementations = {}

        if "cloud" not in self._implementations:
            return await self.async_step_pat_implementation()

        if user_input is not None:
            if user_input["implementation"] == PAT_IMPLEMENTATION:
                return await self.async_step_pat_implementation()
            self.flow_impl = self._implementations["cloud"]
            return await self.async_step_auth()

        options: list[SelectOptionDict] = [
            SelectOptionDict(value="cloud", label=self._implementations["cloud"].name),
            SelectOptionDict(value=PAT_IMPLEMENTATION, label="API Access App"),
        ]

        return self.async_show_form(
            step_id="pick_implementation",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        "implementation", default=PAT_IMPLEMENTATION
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_pat_implementation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Use a stored credential automatically, falling back to a personal access token."""
        implementations = {
            key: impl
            for key, impl in self._implementations.items()
            if key != "cloud"
            and getattr(impl, "client_id", None) != HOME_ASSISTANT_CLOUD_CLIENT_ID
        }
        if not implementations:
            return await self.async_step_pat()

        self.flow_impl = next(iter(implementations.values()))
        return await self.async_step_auth()

    async def async_step_pat(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a per-user SmartThings app from a Personal Access Token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self._provision_app(user_input[CONF_PAT_TOKEN])
            except SmartThingsAuthenticationFailedError:
                errors["base"] = "invalid_pat"
            except SmartThingsForbiddenError:
                # TODO: check actual error for unentitled users  # pylint: disable=fixme
                errors["base"] = "entitlement_required"
            except SmartThingsConnectionError:
                errors["base"] = "cannot_connect"
            except SmartThingsQuotaExceededError:
                errors["base"] = "quota_exceeded"
            else:
                return await self.async_step_auth()
        return self.async_show_form(
            step_id="pat",
            data_schema=probatio.Schema({probatio.Required(CONF_PAT_TOKEN): str}),
            errors=errors,
            description_placeholders={
                "token_url": PAT_TOKEN_URL,
                "manage_plans_url": MANAGE_PLANS_URL,
            },
        )

    async def _provision_app(self, pat: str) -> None:
        """Provision a per-user OAuth app for the given Personal Access Token."""
        redirect_uri = async_get_redirect_uri(self.hass)
        client = SmartThings(session=async_get_clientsession(self.hass))
        client.authenticate(pat)

        ledger = await async_get_app_ledger(self.hass)
        # await ledger.async_reconcile(client)

        apps = await client.list_apps()
        existing_app = next(
            (app for app in apps if app.app_name.startswith(APP_NAME_PREFIX)), None
        )

        if existing_app is not None:
            self._app_id = existing_app.app_id
            regenerated = await client.regenerate_oauth(
                existing_app.app_id, "Home Assistant", REQUESTED_SCOPES
            )
            client_id = regenerated.client_id
            client_secret = regenerated.client_secret
        else:
            app = await client.create_app(
                app_name=APP_NAME_PREFIX + str(uuid4()),
                display_name="Home Assistant",
                description=self.hass.config.location_name,
                redirect_uris=[redirect_uri],
                scopes=REQUESTED_SCOPES,
            )
            self._app_id = app.app_id
            client_id = app.client_id
            client_secret = app.client_secret

        auth_domain = app_auth_domain(self._app_id)

        created_at = dt_util.now().strftime("%b %d, %Y at %H:%M")
        await ledger.async_replace_credential(
            auth_domain,
            ClientCredential(client_id, client_secret, name=f"Created {created_at}"),
        )

        await ledger.async_record(self._app_id)

        implementations = await async_get_implementations(self.hass, DOMAIN)
        self.flow_impl = implementations[auth_domain]

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for SmartThings."""
        if not set(data[CONF_TOKEN]["scope"].split()) >= set(SCOPES):
            return self.async_abort(reason="missing_scopes")
        client = SmartThings(session=async_get_clientsession(self.hass))
        client.authenticate(data[CONF_TOKEN][CONF_ACCESS_TOKEN])
        try:
            locations = await client.get_locations()
        except SmartThingsQuotaExceededError:
            return self.async_abort(
                reason="quota_exceeded",
                description_placeholders={"manage_plans_url": MANAGE_PLANS_URL},
            )
        location = locations[0]
        # We pick to use the location id as unique id rather than the installed app id
        # as the installed app id could change with the right settings in the SmartApp
        # or the app used to sign in changed for any reason.
        await self.async_set_unique_id(location.location_id)
        if self.source != SOURCE_REAUTH:
            self._abort_if_unique_id_configured()

            entry_data: dict[str, Any] = {
                **data,
                CONF_LOCATION_ID: location.location_id,
            }
            if self._app_id is not None:
                entry_data[CONF_APP_ID] = self._app_id
            return self.async_create_entry(
                title=location.name,
                data=entry_data,
            )

        if (entry := self._get_reauth_entry()) and CONF_TOKEN not in entry.data:
            if entry.data[OLD_DATA][CONF_LOCATION_ID] != location.location_id:
                return self.async_abort(reason="reauth_location_mismatch")
            data_updates: dict[str, Any] = {
                **data,
                CONF_LOCATION_ID: location.location_id,
            }
            if self._app_id is not None:
                data_updates[CONF_APP_ID] = self._app_id
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data_updates=data_updates,
                unique_id=location.location_id,
            )
        self._abort_if_unique_id_mismatch(reason="reauth_account_mismatch")
        data_updates = dict(data)
        if self._app_id is not None:
            data_updates[CONF_APP_ID] = self._app_id
        return self.async_update_reload_and_abort(
            self._get_reauth_entry(), data_updates=data_updates
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon migration of old entries."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
            )
        entry = self._get_reauth_entry()
        if "auth_implementation" in entry.data:
            try:
                self.flow_impl = await async_get_config_entry_implementation(
                    self.hass, entry
                )
            except ValueError, ImplementationUnavailableError:
                return await self.async_step_user()
            return await self.async_step_auth()
        return await self.async_step_user()
