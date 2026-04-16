"""DataUpdateCoordinator for the blanco integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging
from typing import Any

from blanco_smart_home_api_client import (
    BlancoApiClient,
    BlancoApiError,
    BlancoConnectionError,
    BlancoErrorType,
    BlancoTokenExpiredError,
    HttpStatus,
)

from homeassistant.config_entries import ConfigEntry, ConfigEntryAuthFailed
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_DEV_ID, CONF_DEV_TYPE, CONF_TOKEN, CONF_TOKEN_TYPE, DOMAIN
from .definitions import BlancoDeviceType

_LOGGER = logging.getLogger(__name__)


UPDATE_INTERVAL = timedelta(seconds=30)
"""Poll interval for the BLANCO device data endpoints."""


class BlancoDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that polls the BLANCO device system and status endpoints."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
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
        )
        self._entry = entry
        self.dev_id = dev_id
        self.serial = serial
        try:
            self.dev_type = BlancoDeviceType(dev_type) if dev_type is not None else None
        except ValueError:
            self.dev_type = BlancoDeviceType.UNDEF

        session = async_get_clientsession(hass)
        self._api = BlancoApiClient(
            session,
            app_id=app_id,
            token=token,
            token_type=token_type,
            app_version=app_version,
            app_build=app_build,
            os_version=HA_VERSION,
        )

    async def _async_renew_token(self) -> bool:
        """Re-authenticate using the stored dev_id and update the token in entry.data.

        Returns True if the token was successfully renewed, False otherwise.
        """
        _LOGGER.debug("Attempting token renewal...")
        try:
            auth = await self._api.renew_token(self._entry.data[CONF_DEV_ID])
        except BlancoApiError as err:
            _LOGGER.error("Token renewal failed: %s", err)
            return False

        new_token = auth["token"]
        new_token_type = auth["token_type"]
        # Persist renewed token in entry.data.
        self.hass.config_entries.async_update_entry(
            self._entry,
            data={
                **self._entry.data,
                CONF_TOKEN: new_token,
                CONF_TOKEN_TYPE: new_token_type,
            },
        )
        # Update authorization in api client for subsequent requests.
        self._api.update_authorization(new_token, new_token_type)
        _LOGGER.debug("Token successfully renewed")
        return True

    async def _async_get_with_retry(
        self,
        api_method: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
    ) -> Any:
        """Call an api client GET method; retry once after token renewal on 401.

        Raises:
            ConfigEntryAuthFailed: When a 401 is received and token renewal fails.
            BlancoConnectionError: Propagated from the api method on network failure.
        """
        try:
            return await api_method(*args)
        except BlancoTokenExpiredError:
            _LOGGER.warning("Token expired, attempting renewal...")
            if not await self._async_renew_token():
                raise ConfigEntryAuthFailed(
                    "Token renewal failed — reauthentication required"
                ) from None
            return await api_method(*args)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch system, status, settings, and errors from the BLANCO API."""
        prev: dict[str, Any] = self.data or {}

        # ── /system ───────────────────────────────────────────────────────────
        try:
            status, result = await self._async_get_with_retry(
                self._api.get_device_system, self.dev_id
            )
            if status == HttpStatus.OK:
                system_data: dict[str, Any] = dict(result)
            else:
                _LOGGER.warning(
                    "System endpoint returned HTTP %s, using previous data", status
                )
                system_data = prev.get("system", {"params": {}, "info": {}})
        except BlancoConnectionError as err:
            _LOGGER.warning("GET /system failed: %s, using previous data", err)
            system_data = prev.get("system", {"params": {}, "info": {}})

        # ── /status ───────────────────────────────────────────────────────────
        try:
            status, result = await self._async_get_with_retry(
                self._api.get_device_status, self.dev_id
            )
            if status == HttpStatus.OK:
                status_data: dict[str, Any] = dict(result)
            else:
                _LOGGER.warning(
                    "Status endpoint returned HTTP %s, using previous data", status
                )
                status_data = prev.get("status", {"params": {}, "info": {}})
        except BlancoConnectionError as err:
            _LOGGER.warning("GET /status failed: %s, using previous data", err)
            status_data = prev.get("status", {"params": {}, "info": {}})

        # ── /settings ─────────────────────────────────────────────────────────
        try:
            status, result = await self._async_get_with_retry(
                self._api.get_device_settings, self.dev_id
            )
            if status == HttpStatus.OK:
                settings_data: dict[str, Any] = dict(result)
            else:
                _LOGGER.warning(
                    "Settings endpoint returned HTTP %s, using previous data", status
                )
                settings_data = prev.get("settings", {"params": {}, "info": {}})
        except BlancoConnectionError as err:
            _LOGGER.warning("GET /settings failed: %s, using previous data", err)
            settings_data = prev.get("settings", {"params": {}, "info": {}})

        # ── /errors ───────────────────────────────────────────────────────────
        try:
            status, result = await self._async_get_with_retry(
                self._api.get_device_errors, self.dev_id
            )
            if status == HttpStatus.OK:
                errors_data: dict[str, Any] = dict(result)
            else:
                _LOGGER.warning(
                    "Errors endpoint returned HTTP %s, using previous data", status
                )
                errors_data = prev.get("errors", {"errors": [], "info": {}})
        except BlancoConnectionError as err:
            _LOGGER.warning("GET /errors failed: %s, using previous data", err)
            errors_data = prev.get("errors", {"errors": [], "info": {}})

        # ── repair issues ─────────────────────────────────────────────────────
        active_errors = [
            e
            for e in errors_data.get("errors", [])
            if e.get("err_type") in (BlancoErrorType.CRITICAL, BlancoErrorType.WARNING)
        ]
        repair_issue_id = f"device_error_{self.dev_id}"
        device_name = system_data.get("params", {}).get("dev_name") or self._entry.title
        if active_errors:
            async_create_issue(
                self.hass,
                DOMAIN,
                repair_issue_id,
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="device_error",
                translation_placeholders={
                    "device_name": device_name,
                    "error_count": str(len(active_errors)),
                },
            )
        else:
            async_delete_issue(self.hass, DOMAIN, repair_issue_id)

        # ── dev_type discovery ────────────────────────────────────────────────
        if self.dev_type is None:
            for candidate_data in (
                system_data,
                status_data,
                settings_data,
                errors_data,
            ):
                raw = candidate_data.get("info", {}).get("dev_type")
                if raw is not None:
                    try:
                        self.dev_type = BlancoDeviceType(raw)
                    except ValueError:
                        self.dev_type = BlancoDeviceType.UNDEF
                    self.hass.config_entries.async_update_entry(
                        self._entry,
                        data={**self._entry.data, CONF_DEV_TYPE: raw},
                    )
                    break

        return {
            "system": system_data,
            "status": status_data,
            "settings": settings_data,
            "errors": errors_data,
        }
