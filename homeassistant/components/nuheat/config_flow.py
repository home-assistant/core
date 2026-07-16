"""OAuth config flow for NuHeat."""

from collections.abc import Mapping
import logging
from typing import Any, override

from chemelex_nuheat import (
    NuHeatApiError,
    NuHeatAuthError,
    NuHeatClient,
    NuHeatDataError,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from .account_identity import (
    InvalidAccountSubjectError,
    account_subject_from_entry_data,
)
from .const import DOMAIN, OAUTH_SCOPES
from .migration import (
    OAUTH_CONFIG_ENTRY_VERSION,
    MigrationAccountMismatchError,
    async_consolidate_legacy_entries,
    is_legacy_entry,
)

_LOGGER = logging.getLogger(__name__)


class NuHeatConfigFlow(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle NuHeat OAuth2 setup, migration, and reauthentication."""

    DOMAIN = DOMAIN
    VERSION = OAUTH_CONFIG_ENTRY_VERSION

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start with any HA-registered local or cloud OAuth provider."""
        if user_input is None:
            try:
                implementations = (
                    await config_entry_oauth2_flow.async_get_implementations(
                        self.hass, DOMAIN
                    )
                )
            except ImplementationUnavailableError:
                return self.async_abort(reason="oauth_implementation_unavailable")
            if not implementations:
                return self.async_abort(reason="missing_oauth_credentials")
        return await super().async_step_user(user_input)

    @property
    @override
    def logger(self) -> logging.Logger:
        return _LOGGER

    @property
    @override
    def extra_authorize_data(self) -> dict[str, str]:
        return {"scope": " ".join(OAUTH_SCOPES)}

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        token = data[CONF_TOKEN]

        try:
            unique_id = account_subject_from_entry_data(data)
        except InvalidAccountSubjectError:
            return self.async_abort(reason="invalid_account_identity")

        async def async_access_token(force_refresh: bool) -> str:
            return token[CONF_ACCESS_TOKEN]

        api = NuHeatClient(async_get_clientsession(self.hass), async_access_token)
        try:
            account = await api.get_account()
            thermostats = await api.list_thermostats()
        except NuHeatAuthError:
            return self.async_abort(reason="invalid_auth")
        except NuHeatApiError, NuHeatDataError:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(unique_id)

        if self.source == SOURCE_REAUTH:
            entry = self._get_reauth_entry()
            if is_legacy_entry(entry):
                try:
                    await async_consolidate_legacy_entries(
                        self.hass,
                        entry,
                        oauth_data=data,
                        account_unique_id=unique_id,
                        account_title=account.username,
                        thermostats=thermostats,
                    )
                except MigrationAccountMismatchError:
                    return self.async_abort(reason="migration_account_mismatch")
                except Exception:  # noqa: BLE001
                    return self.async_abort(reason="migration_failed")
                return self.async_abort(reason="migration_successful")

            if entry.unique_id != unique_id:
                try:
                    stored_subject = account_subject_from_entry_data(entry.data)
                except InvalidAccountSubjectError:
                    stored_subject = None
                if stored_subject == unique_id:
                    self.hass.config_entries.async_update_entry(
                        entry,
                        unique_id=unique_id,
                        version=OAUTH_CONFIG_ENTRY_VERSION,
                    )
            self._abort_if_unique_id_mismatch(reason="reauth_account_mismatch")
            self.hass.config_entries.async_update_entry(
                entry, version=OAUTH_CONFIG_ENTRY_VERSION
            )
            return self.async_update_reload_and_abort(
                entry, title=account.username, data=data
            )

        for existing_entry in self.hass.config_entries.async_entries(DOMAIN):
            if existing_entry.unique_id == unique_id:
                continue
            try:
                stored_subject = account_subject_from_entry_data(existing_entry.data)
            except InvalidAccountSubjectError:
                continue
            if stored_subject == unique_id:
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    unique_id=unique_id,
                    version=OAUTH_CONFIG_ENTRY_VERSION,
                )
                break
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=account.username, data=data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication."""
        if is_legacy_entry(self._get_reauth_entry()):
            return await self.async_step_migration_confirm()
        return await self.async_step_reauth_confirm()

    async def async_step_migration_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask a legacy user to replace obsolete credentials with OAuth."""
        entry = self._get_reauth_entry()
        if user_input is None:
            return self.async_show_form(
                step_id="migration_confirm",
                data_schema=vol.Schema({}),
                description_placeholders={"thermostat": entry.title},
            )
        return await self.async_step_user()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to relink the existing account."""
        entry = self._get_reauth_entry()
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
                description_placeholders={"account": entry.title},
            )
        return await self.async_step_pick_implementation(
            {"implementation": entry.data["auth_implementation"]}
        )
