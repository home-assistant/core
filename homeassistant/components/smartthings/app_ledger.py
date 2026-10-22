"""Track per-user SmartThings apps provisioned during config flow setup."""

import asyncio
import logging
from typing import Any, TypedDict, override

from homeassistant.components.application_credentials import (
    CONF_AUTH_DOMAIN,
    DATA_COMPONENT as APPLICATION_CREDENTIALS_DATA_COMPONENT,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.const import CONF_DOMAIN, CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.singleton import singleton
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, app_auth_domain

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_MINOR_VERSION = 2
STORAGE_KEY = f"{DOMAIN}.app_ledger"


class AppLedgerData(TypedDict):
    """Storage schema for the app ledger."""

    apps: dict[str, str]


class _AppLedgerStore(Store[AppLedgerData]):
    """Store for the app ledger, migrating older formats."""

    @override
    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> AppLedgerData:
        """Migrate to the latest version."""
        if old_minor_version < 2:
            # The redirect URI of these apps is unknown, so they are never reused.
            return {"apps": dict.fromkeys(old_data["app_ids"], "")}
        return old_data  # type: ignore[return-value]


class SmartThingsAppLedger:
    """Track every SmartThings app this Home Assistant instance has provisioned."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the app ledger."""
        self.hass = hass
        self._store = _AppLedgerStore(
            hass, STORAGE_VERSION, STORAGE_KEY, minor_version=STORAGE_MINOR_VERSION
        )
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

    async def async_record(self, app_id: str, redirect_uri: str) -> None:
        """Record a provisioned app id and the redirect URI it was created with."""
        await self.async_load()
        assert self._data is not None
        if self._data["apps"].get(app_id) != redirect_uri:
            self._data["apps"][app_id] = redirect_uri
            await self.async_save()

    async def async_replace_credential(
        self, auth_domain: str, credential: ClientCredential
    ) -> None:
        """Replace any existing stored credential for an auth_domain with a new one."""
        credentials = self.hass.data[APPLICATION_CREDENTIALS_DATA_COMPONENT]
        for item in credentials.async_items():
            if item[CONF_DOMAIN] != DOMAIN:
                continue
            if item.get(CONF_AUTH_DOMAIN, item[CONF_ID]) != auth_domain:
                continue
            try:
                await credentials.async_delete_item(item[CONF_ID])
            except HomeAssistantError:
                _LOGGER.debug(
                    "Could not delete existing credential %s before replacing it",
                    auth_domain,
                )
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
