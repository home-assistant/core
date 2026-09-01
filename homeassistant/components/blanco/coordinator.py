"""DataUpdateCoordinator for the blanco integration."""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any, override

if TYPE_CHECKING:
    from . import BlancoConfigEntry

from blanco_smart_home_api_client import (
    BlancoApiClient,
    BlancoApiError,
    BlancoConnectionError,
    BlancoDeviceType,
    HttpStatus,
)

from homeassistant.const import (
    CONF_TOKEN,
    EVENT_CORE_CONFIG_UPDATE,
    __version__ as HA_VERSION,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_APP_LOCALE, CONF_TOKEN_TYPE, DOMAIN

_LOGGER = logging.getLogger(__name__)


UPDATE_INTERVAL = timedelta(seconds=30)


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
        dev_type: int | None,
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
        try:
            self.dev_type = BlancoDeviceType(dev_type) if dev_type is not None else None
        except ValueError:
            self.dev_type = None

        session = async_get_clientsession(hass)
        self._api = BlancoApiClient(
            session,
            app_id=app_id,
            token=token,
            token_type=token_type,
            dev_id=dev_id,
            app_version=app_version,
            app_build=app_build,
            os_version=HA_VERSION,
            on_token_renewed=self._persist_renewed_token,
        )
        self._setup_language_listener()

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

    def _setup_language_listener(self) -> None:
        """Listen for HA language changes and notify the BLANCO API via PUT."""

        async def _handle_core_config_update(event: Event) -> None:
            """Update the app locale on the BLANCO API when HA language changes."""
            if "language" not in event.data:
                return

            new_locale = self.hass.config.language.split("-")[0][:2]
            if new_locale == self.config_entry.data.get(CONF_APP_LOCALE):
                return

            try:
                success = await self._api.update_app_locale(new_locale)
            except BlancoConnectionError:
                return  # failure already logged by the API client
            if success:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, CONF_APP_LOCALE: new_locale},
                )

        self.config_entry.async_on_unload(
            self.hass.bus.async_listen(
                EVENT_CORE_CONFIG_UPDATE, _handle_core_config_update
            )
        )

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch system and errors from the BLANCO API."""
        prev: dict[str, Any] = self.data or {}
        fresh_count = 0

        # ── /system ───────────────────────────────────────────────────────────
        try:
            status, result = await self._api.get_device_system(self.dev_id)
            if status == HttpStatus.OK:
                system_data: dict[str, Any] = dict(result)
                fresh_count += 1
            else:
                _LOGGER.warning(
                    "System endpoint returned HTTP %s, using previous data", status
                )
                system_data = prev.get("system", {"params": {}, "info": {}})
        except BlancoConnectionError as err:
            _LOGGER.warning("GET /system failed: %s, using previous data", err)
            system_data = prev.get("system", {"params": {}, "info": {}})
        except BlancoApiError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="token_expired",
            ) from err

        # ── /errors ───────────────────────────────────────────────────────────
        try:
            status, result = await self._api.get_device_errors(self.dev_id)
            if status == HttpStatus.OK:
                errors_data: dict[str, Any] = dict(result)
                fresh_count += 1
            else:
                _LOGGER.warning(
                    "Errors endpoint returned HTTP %s, using previous data", status
                )
                errors_data = prev.get("errors", {"errors": [], "info": {}})
        except BlancoConnectionError as err:
            _LOGGER.warning("GET /errors failed: %s, using previous data", err)
            errors_data = prev.get("errors", {"errors": [], "info": {}})
        except BlancoApiError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="token_expired",
            ) from err

        if fresh_count == 0:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            )

        return {
            "system": system_data,
            "errors": errors_data,
        }
