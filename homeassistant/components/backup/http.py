"""Http view for the Backup integration."""

from __future__ import annotations

import asyncio
from http import HTTPStatus
from typing import cast

from aiohttp import BodyPartReader
from aiohttp.hdrs import CONTENT_DISPOSITION
from aiohttp.web import FileResponse, Request, Response

from homeassistant.components.http import KEY_HASS, HomeAssistantView, require_admin
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from .const import DATA_MANAGER


@callback
def async_register_http_views(hass: HomeAssistant) -> None:
    """Register the http views."""
    hass.http.register_view(DownloadBackupView)
    hass.http.register_view(UploadBackupView)


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

        manager = request.app[KEY_HASS].data[DATA_MANAGER]
        backup = await manager.async_get_backup(slug=slug)

        if backup is None or not backup.path.exists():
            return Response(status=HTTPStatus.NOT_FOUND)

        return FileResponse(
            path=backup.path.as_posix(),
            headers={
                CONTENT_DISPOSITION: f"attachment; filename={slugify(backup.name)}.tar"
            },
        )


class UploadBackupView(HomeAssistantView):
    """Generate backup view."""

    url = "/api/backup/upload"
    name = "api:backup:upload"

    @require_admin
    async def post(self, request: Request) -> Response:
        """Upload a backup file."""
        manager = request.app[KEY_HASS].data[DATA_MANAGER]
        reader = await request.multipart()
        contents = cast(BodyPartReader, await reader.next())

        try:
            await manager.async_receive_backup(contents=contents)
        except OSError as err:
            return Response(
                body=f"Can't write backup file {err}",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        except asyncio.CancelledError:
            return Response(status=HTTPStatus.INTERNAL_SERVER_ERROR)

        return Response(status=HTTPStatus.CREATED)
