"""Backup onboarding views."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from functools import wraps
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Concatenate

from aiohttp import web
from aiohttp.web_exceptions import HTTPUnauthorized
import voluptuous as vol

from homeassistant.components.http import KEY_HASS
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.components.onboarding import (
    BaseOnboardingView,
    NoAuthBaseOnboardingView,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.backup import async_get_manager as async_get_backup_manager

from . import BackupManager, Folder, IncorrectPasswordError, http as backup_http

if TYPE_CHECKING:
    from homeassistant.components.onboarding import OnboardingStoreData


async def async_setup_views(hass: HomeAssistant, data: OnboardingStoreData) -> None:
    """Set up the backup views."""

    hass.http.register_view(BackupInfoView(data))
    hass.http.register_view(RestoreBackupView(data))
    hass.http.register_view(UploadBackupView(data))


def with_backup_manager[_ViewT: BaseOnboardingView, **_P](
    func: Callable[
        Concatenate[_ViewT, BackupManager, web.Request, _P],
        Coroutine[Any, Any, web.Response],
    ],
) -> Callable[Concatenate[_ViewT, web.Request, _P], Coroutine[Any, Any, web.Response]]:
    """Home Assistant API decorator to check onboarding and inject manager."""

    @wraps(func)
    async def with_backup(
        self: _ViewT,
        request: web.Request,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> web.Response:
        """Check admin and call function."""
        if self._data["done"]:
            raise HTTPUnauthorized

        manager = await async_get_backup_manager(request.app[KEY_HASS])
        return await func(self, manager, request, *args, **kwargs)

    return with_backup


class BackupInfoView(NoAuthBaseOnboardingView):
    """Get backup info view."""

    url = "/api/onboarding/backup/info"
    name = "api:onboarding:backup:info"

    @with_backup_manager
    async def get(self, manager: BackupManager, request: web.Request) -> web.Response:
        """Return backup info."""
        backups, _ = await manager.async_get_backups()
        return self.json(
            {
                "backups": list(backups.values()),
                "state": manager.state,
                "last_action_event": manager.last_action_event,
            }
        )


class RestoreBackupView(NoAuthBaseOnboardingView):
    """Restore backup view."""

    url = "/api/onboarding/backup/restore"
    name = "api:onboarding:backup:restore"

    @RequestDataValidator(
        vol.Schema(
            {
                vol.Required("backup_id"): str,
                vol.Required("agent_id"): str,
                vol.Optional("password"): str,
                vol.Optional("restore_addons"): [str],
                vol.Optional("restore_database", default=True): bool,
                vol.Optional("restore_folders"): [vol.Coerce(Folder)],
            }
        )
    )
    @with_backup_manager
    async def post(
        self, manager: BackupManager, request: web.Request, data: dict[str, Any]
    ) -> web.Response:
        """Restore a backup."""
        try:
            await manager.async_restore_backup(
                data["backup_id"],
                agent_id=data["agent_id"],
                password=data.get("password"),
                restore_addons=data.get("restore_addons"),
                restore_database=data["restore_database"],
                restore_folders=data.get("restore_folders"),
                restore_homeassistant=True,
            )
        except IncorrectPasswordError:
            return self.json(
                {"code": "incorrect_password"}, status_code=HTTPStatus.BAD_REQUEST
            )
        except HomeAssistantError as err:
            return self.json(
                {"code": "restore_failed", "message": str(err)},
                status_code=HTTPStatus.BAD_REQUEST,
            )
        return web.Response(status=HTTPStatus.OK)


class UploadBackupView(NoAuthBaseOnboardingView, backup_http.UploadBackupView):
    """Upload backup view."""

    url = "/api/onboarding/backup/upload"
    name = "api:onboarding:backup:upload"

    @with_backup_manager
    async def post(self, manager: BackupManager, request: web.Request) -> web.Response:
        """Upload a backup file."""
        return await self._post(request)
