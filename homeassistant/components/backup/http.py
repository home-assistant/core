"""Http view for the Backup integration."""

from __future__ import annotations

from http import HTTPStatus

from aiohttp.hdrs import CONTENT_DISPOSITION
from aiohttp.web import FileResponse, Request, Response

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from .const import DOMAIN
from .manager import BackupManager


@callback
def async_register_http_views(hass: HomeAssistant) -> None:
    """Register the http views."""
    hass.http.register_view(DownloadBackupView)


class DownloadBackupView(HomeAssistantView):
    """Generate backup view."""

    url = "/api/backup/download/{slug}"
    name = "api:backup:download"

    async def get(
        self,
        request: Request,
        slug: str,
    ) -> FileResponse | Response:
        """Download a backup file."""
        if not request["hass_user"].is_admin:
            return Response(status=HTTPStatus.UNAUTHORIZED)

        manager: BackupManager = request.app[KEY_HASS].data[DOMAIN]
        backup = await manager.get_backup(slug)

        if backup is None or not backup.path.exists():
            return Response(status=HTTPStatus.NOT_FOUND)

        return FileResponse(
            path=backup.path.as_posix(),
            headers={
                CONTENT_DISPOSITION: f"attachment; filename={slugify(backup.name)}.tar"
            },
        )
