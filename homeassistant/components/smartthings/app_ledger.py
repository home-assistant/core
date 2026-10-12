"""Track per-user SmartThings apps provisioned during config flow setup."""

import logging
from typing import TypedDict

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

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.app_ledger"


class AppLedgerData(TypedDict):
    """Storage schema for the app ledger."""

    app_ids: list[str]


class SmartThingsAppLedger:
    """Track every SmartThings app this Home Assistant instance has provisioned."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the app ledger."""
        self.hass = hass
        self._store = Store[AppLedgerData](hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: AppLedgerData | None = None

    async def async_load(self) -> None:
        """Load the ledger from storage."""
        if self._data is None:
            self._data = await self._store.async_load() or {"app_ids": []}

    async def async_save(self) -> None:
        """Persist the ledger to storage."""
        assert self._data is not None
        await self._store.async_save(self._data)

    async def async_record(self, app_id: str) -> None:
        """Record a newly provisioned app id."""
        await self.async_load()
        assert self._data is not None
        if app_id not in self._data["app_ids"]:
            self._data["app_ids"].append(app_id)
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
