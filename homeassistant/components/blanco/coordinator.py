"""DataUpdateCoordinator for the blanco integration."""

from datetime import timedelta
import logging
from typing import Any, override

from blanco_smart_home_api_client import (
    BlancoApiClient,
    BlancoApiError,
    BlancoConnectionError,
    HttpStatus,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_TOKEN_TYPE, DOMAIN

_LOGGER = logging.getLogger(__name__)


UPDATE_INTERVAL = timedelta(seconds=30)

type BlancoConfigEntry = ConfigEntry[BlancoDataUpdateCoordinator]


class BlancoDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that polls the BLANCO device system and errors endpoints."""

    config_entry: BlancoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BlancoConfigEntry,
        token: str,
        token_type: str,
        dev_id: str,
        dev_type: int,
        serial: str,
        app_id: str,
        app_version: str = "",
        app_build: str = "",
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="blanco",
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.dev_id = dev_id
        self.serial = serial
        self.dev_type = dev_type

        self._api = BlancoApiClient(
            async_get_clientsession(hass),
            app_id=app_id,
            token=token,
            token_type=token_type,
            dev_id=dev_id,
            app_version=app_version,
            app_build=app_build,
            os_version=HA_VERSION,
            on_token_renewed=self._persist_renewed_token,
        )

    def _persist_renewed_token(self, token: str, token_type: str) -> None:
        """Persist a token the API client renewed automatically into entry.data."""
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={
                **self.config_entry.data,
                CONF_TOKEN: token,
                CONF_TOKEN_TYPE: token_type,
            },
        )

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch system and errors from the BLANCO API."""
        prev: dict[str, Any] = self.data or {}

        system_data: dict[str, Any] = prev.get("system", {"params": {}, "info": {}})
        try:
            status, result = await self._api.get_device_system(self.dev_id)
        except BlancoConnectionError as err:
            _LOGGER.debug("Fetching device system data failed: %s", err)
        except BlancoApiError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="token_expired",
            ) from err
        else:
            if status == HttpStatus.OK:
                system_data = dict(result)
            else:
                _LOGGER.debug("Device system endpoint returned HTTP %s", status)

        try:
            status, result = await self._api.get_device_errors(self.dev_id)
        except BlancoConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err
        except BlancoApiError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="token_expired",
            ) from err
        if status != HttpStatus.OK:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            )
        errors_data: dict[str, Any] = dict(result)

        return {
            "system": system_data,
            "errors": errors_data,
        }
