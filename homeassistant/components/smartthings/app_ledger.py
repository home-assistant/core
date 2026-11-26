"""Track per-user SmartThings apps provisioned during config flow setup."""

import asyncio
from typing import TypedDict

from homeassistant.components.application_credentials import (
    CONF_AUTH_DOMAIN,
    DATA_COMPONENT as APPLICATION_CREDENTIALS_DATA_COMPONENT,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.const import CONF_DOMAIN, CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.singleton import singleton
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, app_auth_domain

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.app_ledger"


class AppLedgerData(TypedDict):
    """Storage schema for the app ledger."""

    apps: dict[str, str]


class SmartThingsAppLedger:
    """Track every SmartThings app this Home Assistant instance has provisioned."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the app ledger."""
        self.hass = hass
        self._store = Store[AppLedgerData](hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: AppLedgerData | None = None
        self.provisioning_lock = asyncio.Lock()

    async def async_load(self) -> None:
        """Load the ledger from storage."""
        if self._data is None:
            self._data = await self._store.async_load() or {"apps": {}}

    async def async_save(self) -> None:
        """Persist the ledger to storage."""
        assert self._data is not None
        await self._store.async_save(self._data)

    def is_reusable(self, app_id: str, redirect_uri: str) -> bool:
        """Return if this instance provisioned the app for the given redirect URI."""
        assert self._data is not None
        return self._data["apps"].get(app_id) == redirect_uri

    def is_provisioned_auth_domain(self, auth_domain: str) -> bool:
        """Return if the auth_domain belongs to an app this instance provisioned."""
        assert self._data is not None
        return any(
            app_auth_domain(app_id) == auth_domain for app_id in self._data["apps"]
        )

    def is_stale(self, auth_domain: str, redirect_uri: str) -> bool:
        """Return if the auth_domain's app was provisioned for another redirect URI."""
        assert self._data is not None
        return any(
            app_auth_domain(app_id) == auth_domain and app_redirect_uri != redirect_uri
            for app_id, app_redirect_uri in self._data["apps"].items()
        )

    async def async_record(self, app_id: str, redirect_uri: str) -> None:
        """Record a provisioned app id and the redirect URI it was created with."""
        await self.async_load()
        assert self._data is not None
        if self._data["apps"].get(app_id) != redirect_uri:
            self._data["apps"][app_id] = redirect_uri
            await self.async_save()

    def _credential_ids(self, auth_domain: str) -> list[str]:
        """Return the ids of stored credentials for an auth_domain."""
        credentials = self.hass.data[APPLICATION_CREDENTIALS_DATA_COMPONENT]
        return [
            item[CONF_ID]
            for item in credentials.async_items()
            if item[CONF_DOMAIN] == DOMAIN
            and item.get(CONF_AUTH_DOMAIN, item[CONF_ID]) == auth_domain
        ]

    async def async_remove_unused_credential(self, auth_domain: str) -> None:
        """Remove a provisioned app's credential once no entry uses it."""
        if not self.is_provisioned_auth_domain(auth_domain) or any(
            entry.data.get("auth_implementation") == auth_domain
            for entry in self.hass.config_entries.async_entries(DOMAIN)
        ):
            return
        credentials = self.hass.data[APPLICATION_CREDENTIALS_DATA_COMPONENT]
        for item_id in self._credential_ids(auth_domain):
            await credentials.async_delete_item(item_id)

    async def async_replace_credential(
        self, auth_domain: str, credential: ClientCredential
    ) -> None:
        """Replace any existing stored credential for an auth_domain with a new one."""
        credentials = self.hass.data[APPLICATION_CREDENTIALS_DATA_COMPONENT]
        for item_id in self._credential_ids(auth_domain):
            await credentials.async_delete_item(item_id)
        await async_import_client_credential(
            self.hass, DOMAIN, credential, auth_domain=auth_domain
        )


KEY_APP_LEDGER: HassKey[SmartThingsAppLedger] = HassKey(f"{DOMAIN}_app_ledger")


@singleton(KEY_APP_LEDGER, async_=True)
async def async_get_app_ledger(hass: HomeAssistant) -> SmartThingsAppLedger:
    """Get the SmartThings app ledger for this Home Assistant instance."""
    ledger = SmartThingsAppLedger(hass)
    await ledger.async_load()
    return ledger
